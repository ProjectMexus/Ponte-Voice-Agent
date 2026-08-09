import inspect
from copy import deepcopy
import unittest

from middleware.contracts import ToolExecutionResult
from middleware.cash_sharing_workflow import CashSharingWorkflow
from middleware.intent import IntentDecision
from middleware.interaction_contracts import CanonicalInteractionResult, EventEnvelope
from middleware.interaction_core import InteractionCore
from middleware.interaction_delivery import WorkspaceProjector
from middleware.medical_workflow import MedicalWorkflow
from middleware.session import SessionStore
from middleware.tests.test_cash_sharing_workflow import FakeCashPipeline
from middleware.tests.test_medical_workflow import FakePipeline as MedicalPipeline


class FakeIntentRecognizer:
    def __init__(self, intent="medical_booking"):
        self.intent = intent

    def recognize(self, message):
        return IntentDecision(self.intent, "keyword", 1.0, "medical")


class FakePipeline:
    def __init__(self):
        self.calls = []

    def dispatch(self, call):
        self.calls.append(call)
        if call.name == "medical.list_appointment_services":
            return ToolExecutionResult(call.name, call.step_id, True, "REQ-SERVICES", {
                "data": [{"id": "SERVICE-US-001", "name": "腹部超聲波檢查", "active": True}],
            })
        raise AssertionError(f"unexpected tool: {call.name}")


class FakeWorkflow:
    def __init__(self):
        self.started = []
        self.handled = []

    def start(self, envelope, intent):
        self.started.append((envelope, intent))
        return self._outcome(envelope, "select_service")

    def handle(self, task, envelope):
        self.handled.append((task, envelope))
        updated = dict(task)
        updated["current_step"] = "select_slot"
        return self._outcome(envelope, "select_slot", updated)

    @staticmethod
    def _outcome(envelope, response_intent, task=None):
        task = task or {
            "task_id": "TASK-1",
            "type": "medical_appointment",
            "status": "awaiting_input",
            "current_step": "select_service",
            "facts": {},
        }
        result = CanonicalInteractionResult(
            interaction_id=envelope.interaction_id,
            task=task,
            response_intent=response_intent,
        )
        return task, result, [{"type": "workflow_called"}]


def envelope(session_id, interaction_id, event):
    return EventEnvelope.from_json({
        "routing": {"session_id": session_id, "interaction_id": interaction_id},
        "event": event,
    })


def build_real_core(pipeline=None):
    workflow = MedicalWorkflow(
        pipeline or FakePipeline(),
        "PAT-DEMO-001",
        "Bearer demo",
        mock_user_id="USR-DEMO-001",
    )
    return InteractionCore(
        SessionStore(),
        workflow,
        intent_recognizer=FakeIntentRecognizer(),
    )


class InteractionCoreTests(unittest.TestCase):
    def test_core_starts_selected_workflow_and_saves_returned_task(self):
        sessions = SessionStore()
        workflow = FakeWorkflow()
        core = InteractionCore(sessions, workflow, intent_recognizer=FakeIntentRecognizer())

        result = core.handle(envelope("S-1", "INT-1", {
            "type": "user_utterance", "content": "我想預約醫療服務",
        }))

        state = sessions.get_or_create("S-1")
        self.assertEqual(len(workflow.started), 1)
        self.assertEqual(state.active_task_id, "TASK-1")
        self.assertEqual(state.task, result.task)
        self.assertEqual(state.interaction_log, [{"type": "workflow_called"}])

    def test_core_routes_existing_task_and_saves_workflow_transition(self):
        sessions = SessionStore()
        workflow = FakeWorkflow()
        core = InteractionCore(sessions, workflow, intent_recognizer=FakeIntentRecognizer())
        core.handle(envelope("S-1", "INT-1", {
            "type": "user_utterance", "content": "我想預約醫療服務",
        }))

        result = core.handle(envelope("S-1", "INT-2", {
            "type": "service_selected", "action_id": "ACT-1", "task_id": "TASK-1",
            "service_id": "SERVICE-US-001", "date_from": "2026-08-07", "date_to": "2026-08-14",
        }))

        self.assertEqual(len(workflow.handled), 1)
        self.assertEqual(result.task["current_step"], "select_slot")
        self.assertEqual(sessions.get_or_create("S-1").task["current_step"], "select_slot")

    def test_core_rejects_unsupported_intent_without_creating_task(self):
        sessions = SessionStore()
        core = InteractionCore(sessions, FakeWorkflow(), intent_recognizer=FakeIntentRecognizer("cash_sharing"))

        with self.assertRaisesRegex(ValueError, "unsupported interaction intent"):
            core.handle(envelope("S-1", "INT-1", {
                "type": "user_utterance", "content": "現金分享",
            }))

        self.assertIsNone(sessions.get_or_create("S-1").task)

    def test_core_has_no_execution_dependency(self):
        parameters = inspect.signature(InteractionCore.__init__).parameters
        self.assertNotIn("pipeline", parameters)
        self.assertNotIn("executor", parameters)

    def test_cardiology_demo_entry_is_narrow_and_keeps_legacy_tasks(self):
        medical, demo = FakeWorkflow(), FakeWorkflow()
        core = InteractionCore(SessionStore(), medical, demo_workflow=demo,
                               intent_recognizer=FakeIntentRecognizer())
        core.handle(envelope("S-DEMO", "I-1", {
            "type": "user_utterance", "content": "心臟科下週二下午",
        }))
        self.assertEqual(len(demo.started), 1)
        for index, text in enumerate(("我想預約心臟科超聲波檢查", "我的醫療預約中已有心臟科預約")):
            core.handle(envelope(f"S-LEGACY-{index}", f"I-{index+2}", {
                "type": "user_utterance", "content": text,
            }))
        self.assertEqual(len(medical.started), 2)
        self.assertEqual(len(demo.started), 1)
        core.handle(envelope("S-LEGACY-0", "I-4", {
            "type": "user_utterance", "content": "心臟科下週二下午",
        }))
        self.assertEqual(len(medical.handled), 1)
        self.assertEqual(len(demo.started), 1)


class CommonOperationEvidenceTests(unittest.TestCase):
    def test_common_medical_request_and_actions_keep_actual_tool_history(self):
        pipeline = MedicalPipeline()
        core = build_real_core(pipeline)
        first = core.handle(envelope("S-COMMON", "I-1", {
            "type": "user_utterance", "content": "我想預約醫療服務",
        }))
        self.assertEqual([event["operation"] for event in first.facts["service_events"]], ["services"])
        self.assertEqual(WorkspaceProjector.project(first)["activity"], first.facts["service_events"])
        self.assertEqual(len(WorkspaceProjector.project(first)["fields"]), 1)
        selected = core.handle(envelope("S-COMMON", "I-2", {
            "type": "service_selected", "action_id": "ACT-SERVICE", "task_id": first.task["task_id"],
            "service_id": "SERVICE-US-001", "date_from": "2026-08-07", "date_to": "2026-08-14",
        }))
        self.assertEqual([event["operation"] for event in selected.facts["service_events"]], ["services", "slots"])
        confirmation = core.handle(envelope("S-COMMON", "I-3", {
            "type": "slot_selected", "action_id": "ACT-SLOT", "task_id": first.task["task_id"],
            "slot_id": "SLOT-US-20260807-1500",
        }))
        self.assertEqual(confirmation.facts["service_events"], selected.facts["service_events"])
        self.assertIsNotNone(confirmation.confirmation)
        self.assertEqual(len(confirmation.allowed_actions), 3)
        self.assertIsNone(confirmation.receipt)
        self.assertEqual(len(pipeline.calls), 2)
        self.assertEqual([event["id"] for event in confirmation.facts["service_events"]], ["E1", "E2"])
        self.assertEqual(core.sessions.get_or_create("S-COMMON").task, confirmation.task)

    def test_cash_retry_accumulates_observed_calls_and_new_task_starts_its_own_history(self):
        pipeline = FakeCashPipeline(failures=1)
        cash = CashSharingWorkflow(pipeline, "PAT-DEMO-001", "Bearer secret", mock_user_id="USR-DEMO-001")
        core = InteractionCore(SessionStore(), FakeWorkflow(), cash_workflow=cash,
                               intent_recognizer=FakeIntentRecognizer("cash_sharing"))
        first = core.handle(envelope("S-CASH", "I-1", {
            "type": "user_utterance", "content": "我想查現金分享計劃",
        }))
        self.assertEqual(first.facts["service_events"][0]["operation"], "cash")
        self.assertEqual(first.facts["service_events"][0]["status"], "failed")
        retry = next(action["event"] for action in first.allowed_actions if action["event"].get("action") == "retry")
        completed = core.handle(envelope("S-CASH", "I-2", retry))
        self.assertEqual([event["status"] for event in completed.facts["service_events"]], ["failed", "completed"])
        self.assertEqual([event["id"] for event in completed.facts["service_events"]], ["E1", "E2"])
        self.assertEqual(completed.task["status"], "completed")
        self.assertIn("plan", completed.facts)
        self.assertIsNone(completed.receipt)
        self.assertNotIn("Bearer secret", str(WorkspaceProjector.project(completed)))
        new = core.handle(envelope("S-CASH", "I-3", {
            "type": "user_utterance", "content": "再查現金分享計劃",
        }))
        self.assertNotEqual(new.task["task_id"], completed.task["task_id"])
        self.assertEqual([event["id"] for event in new.facts["service_events"]], ["E1"])
        self.assertEqual(new.facts["service_events"][0]["status"], "completed")
        self.assertEqual(len(pipeline.calls), 3)

    def test_evidence_enrichment_preserves_canonical_actions_and_business_state(self):
        core = InteractionCore(SessionStore(), FakeWorkflow())
        state = core.sessions.get_or_create("S-PRESERVE")
        task = {"task_id": "TASK-PRESERVE", "type": "medical_appointment", "status": "completed",
                "current_step": "complete", "facts": {"business_fact": "unchanged"}, "custom_state": [1, 2]}
        original_task = deepcopy(task)
        result = CanonicalInteractionResult("I-PRESERVE", task, "completed", {"public_fact": "unchanged"},
            [{"label": "Issued action", "event": {"action_id": "ACT-SERVER"}}],
            {"confirmation_id": "CONF-SERVER"}, {"reason": "unchanged"}, {"receipt_id": "MED-APT-1"})
        saved = core._save(state, (task, result, [
            {"type": "tool_execution", "tool": "medical.create_appointment", "ok": True},
            {"type": "execution_completed"}, {"type": "receipt_created"},
        ]))
        self.assertEqual(task, original_task)
        self.assertEqual(result.task, original_task)
        self.assertNotIn("service_events", result.facts)
        for key in ("allowed_actions", "confirmation", "recovery", "receipt", "response_intent", "interaction_id"):
            self.assertEqual(getattr(saved, key), getattr(result, key))
        self.assertEqual(saved.facts["public_fact"], "unchanged")
        self.assertEqual(saved.task["facts"]["business_fact"], "unchanged")
        self.assertEqual(saved.task["custom_state"], [1, 2])
        self.assertEqual([event["kind"] for event in saved.facts["service_events"]], ["booking_submitted"])
        self.assertEqual(saved.task, state.task)

    def test_demo_evidence_is_left_exactly_as_returned_by_its_workflow(self):
        core = InteractionCore(SessionStore(), FakeWorkflow())
        state = core.sessions.get_or_create("S-DEMO-EVIDENCE")
        task = {"task_id": "TASK-DEMO", "type": "medical_demo_agent", "status": "awaiting_input",
                "facts": {"service_events": [{"id": "E1", "kind": "draft_prepared", "title": "草稿"}]}}
        result = CanonicalInteractionResult("I-DEMO", task, "slot_selection", deepcopy(task["facts"]))
        saved = core._save(state, (task, result, [
            {"type": "tool_execution", "tool": "medical.list_departments", "ok": True},
        ]))
        self.assertIs(saved, result)
        self.assertEqual(saved.facts["service_events"], task["facts"]["service_events"])
        self.assertEqual(saved.task, state.task)


if __name__ == "__main__":
    unittest.main()
