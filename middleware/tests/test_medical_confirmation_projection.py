"""Exercise delivery projections from a real workflow and in-memory backend."""

import unittest
from datetime import datetime
from unittest.mock import patch

from middleware.contracts import ToolExecutionResult
from middleware.intent import IntentDecision
from middleware.interaction_contracts import EventEnvelope
from middleware.interaction_delivery import DeliveryOrchestrator
from middleware.medical_workflow import MedicalWorkflow
from mock_backends.core.clock import FixedClock, MACAU_TZ
from mock_backends.core.idempotency import RepositoryIdempotencyStore
from mock_backends.core.ids import SequentialIdGenerator
from mock_backends.core.persistence import MemoryRepository
from mock_backends.medical.service import MedicalService


class InProcessMedicalPipeline:
    """Replace only HTTP transport; domain data and transitions stay real."""

    def __init__(self):
        self.service = MedicalService(
            clock=FixedClock(datetime(2026, 8, 3, 9, tzinfo=MACAU_TZ)),
            ids=SequentialIdGenerator(),
            appointment_repository=MemoryRepository(),
            task_repository=MemoryRepository(),
            idempotency=RepositoryIdempotencyStore(MemoryRepository()),
        )

    def dispatch(self, call):
        context = call.arguments["context"]
        values = call.arguments["input"]
        query = {key: [str(value).lower() if isinstance(value, bool) else str(value)] for key, value in values.items()}
        request_id = context["request_id"]
        if call.name == "medical.list_appointment_services":
            response = self.service.list_appointment_services(query, request_id)
        elif call.name == "medical.search_appointment_slots":
            response = self.service.search_appointment_slots(query, request_id)
        elif call.name == "medical.create_appointment":
            response = self.service.create_appointment(context["patient_id"], dict(values), {
                "Idempotency-Key": context["idempotency_key"],
            }, request_id, "/mock/medical/v1/appointments")
        elif call.name == "medical.get_my_appointments":
            response = self.service.list_appointments(context["patient_id"], query, request_id)
        else:
            raise AssertionError(f"Unexpected tool {call.name}")
        return ToolExecutionResult(call.name, call.step_id, response.status < 400, request_id, response.body)


def envelope(identifier, event):
    return EventEnvelope.from_json({
        "routing": {"interaction_id": identifier, "session_id": "S-REAL-MEDICAL"},
        "event": event,
    })


class MedicalConfirmationProjectionTests(unittest.TestCase):
    def setUp(self):
        self.workflow = MedicalWorkflow(InProcessMedicalPipeline(), "PAT-DEMO-001", "Bearer demo")
        self.date_patch = patch("middleware.interaction_delivery._today", return_value="2026-08-03")
        self.horizon_patch = patch("middleware.interaction_delivery._date_plus", return_value="2026-08-17")
        self.date_patch.start()
        self.horizon_patch.start()
        self.addCleanup(self.date_patch.stop)
        self.addCleanup(self.horizon_patch.stop)

    def pending_confirmation(self):
        task, first, _ = self.workflow.start(envelope("INT-1", {
            "type": "user_utterance", "content": "我想預約醫療服務",
        }), IntentDecision("medical_booking", "keyword", 1.0, "medical"))
        service = DeliveryOrchestrator.deliver(first)["workspace"]["fields"][0]["action"]["event"]
        task, second, _ = self.workflow.handle(task, envelope("INT-2", service))
        slot = DeliveryOrchestrator.deliver(second)["workspace"]["fields"][0]["action"]["event"]
        task, pending, _ = self.workflow.handle(task, envelope("INT-3", slot))
        return task, pending

    def complete(self, task, pending):
        approve = next(action["event"] for action in pending.allowed_actions if action["event"].get("decision") == "approve")
        return self.workflow.handle(task, envelope("INT-4", approve))[1]

    def test_review_contains_real_selected_appointment_before_submission(self):
        _, pending = self.pending_confirmation()
        delivered = DeliveryOrchestrator.deliver(pending)
        fields = {field["key"]: field["value"] for field in delivered["workspace"]["fields"]}
        self.assertEqual(fields, {
            "service": "腹部超聲波檢查", "date": "2026-08-12", "time": "14:00", "location": "影像中心",
        })
        self.assertIsNone(delivered["receipt"])
        self.assertEqual(delivered["workspace"]["actions"], pending.allowed_actions)
        self.assertNotIn("CONF-", delivered["response"]["display_text"])
        for value in fields.values():
            self.assertIn(value, delivered["response"]["display_text"])

    def test_confirmation_details_match_created_receipt_and_completion(self):
        task, pending = self.pending_confirmation()
        review = DeliveryOrchestrator.deliver(pending)
        completed = self.complete(task, pending)
        delivered = DeliveryOrchestrator.deliver(completed)
        review_fields = {field["key"]: field["value"] for field in review["workspace"]["fields"]}
        completion_fields = {field["key"]: field["value"] for field in delivered["workspace"]["fields"]}
        for key in ("service", "date", "time", "location"):
            self.assertEqual(review_fields.get(key), delivered["receipt"]["appointment"][key])
            self.assertEqual(completion_fields[key], delivered["receipt"]["appointment"][key])

    def test_saved_appointment_query_keeps_service_and_location_names(self):
        task, pending = self.pending_confirmation()
        self.complete(task, pending)
        _, result, _ = self.workflow.start(envelope("INT-QUERY", {
            "type": "user_utterance", "content": "查詢我的醫療預約",
        }), IntentDecision("medical_query", "keyword", 1.0, "medical"))
        delivered = DeliveryOrchestrator.deliver(result)
        self.assertEqual(delivered["workspace"]["view"], "appointment_list")
        first = delivered["workspace"]["fields"][0]
        self.assertEqual(first["label"], "腹部超聲波檢查")
        self.assertEqual(first["value"], "2026-08-12 · 14:00 · 影像中心 · confirmed")
        self.assertEqual(delivered["workspace"]["actions"], [])


if __name__ == "__main__":
    unittest.main()
