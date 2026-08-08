import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
import threading

from MCP.registry import build_registry
from middleware.contracts import ToolExecutionResult
from middleware.demo_medical_workflow import DemoMedicalWorkflow, after_three
from middleware.demo_model import ScriptedCardiologyClient
from middleware.interaction_contracts import EventEnvelope
from mock_backends.core.clock import FixedClock
from mock_backends.medical.fixtures import cardiology_demo_slots, departments


NOW = datetime(2026, 10, 13, 9, tzinfo=timezone(timedelta(hours=8)))
REQUEST = "心臟科下週二下午"


class MemoryPipeline:
    def __init__(self):
        self.calls = []
        self.slots = cardiology_demo_slots(NOW.date() + timedelta(days=7))
        self.write_result = None

    def dispatch(self, call):
        self.calls.append(call)
        if call.name == "medical.list_departments":
            data = {"data": departments()[:1]}
        elif call.name == "medical.search_registration_slots":
            data = {"data": deepcopy(self.slots)}
        elif call.name == "medical.get_my_appointments":
            data = {"data": []}
        elif call.name == "medical.create_registration":
            if self.write_result is not None:
                return ToolExecutionResult(call.name, call.step_id, False, "REQ", error=self.write_result)
            slot = next(slot for slot in self.slots if slot["id"] == call.arguments["input"]["slot_id"])
            data = {
                "data": {"resourceType": "Appointment", "id": "APT-UNIT", "status": "booked", "patient_id": "PAT-UNIT",
                         "patient": {"id": "PAT-UNIT"}, "department": {"id": "DEPT-CARDIO", "display": "心臟科"},
                         "doctor": {"id": "DOC-002"}, "location": {"display": "第一門診"}, "slot_id": slot["id"],
                         "start": slot["start"], "task_id": "BACKEND-TASK-UNIT"},
                "task": {"resourceType": "Task", "id": "BACKEND-TASK-UNIT", "status": "completed", "patient_id": "PAT-UNIT",
                         "appointment_id": "APT-UNIT", "business_type": "medical_registration"},
                "receipt": {"reference": "MED-REG-UNIT", "issued_at": NOW.isoformat()},
            }
        else:
            raise AssertionError(call.name)
        return ToolExecutionResult(call.name, call.step_id, True, "REQ", data=data)


def envelope(event, session="S-UNIT"):
    return EventEnvelope("I-UNIT", session, event)


class DemoMedicalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.clock = FixedClock(NOW)
        self.pipeline = MemoryPipeline()
        self.workflow = DemoMedicalWorkflow(self.pipeline, "PAT-UNIT", "Bearer test", registry=build_registry(), client=ScriptedCardiologyClient(), clock=self.clock)

    def start(self, content=REQUEST, session="S-UNIT"):
        task, draft, logs = self.workflow.start(envelope({"type": "user_utterance", "content": content}, session))
        if draft.recovery is not None:
            return task, draft, logs
        self.assertIsNone(draft.confirmation)
        self.assertEqual(draft.allowed_actions, [])
        self.assertEqual(self.writes(), [])
        return self.workflow.handle(task, envelope({"type": "user_utterance", "content": "select current slot"}, session))

    @staticmethod
    def approval(result):
        return next(action["event"] for action in result.allowed_actions if action["event"]["decision"] == "approve")

    def writes(self):
        return [call for call in self.pipeline.calls if call.name == "medical.create_registration"]

    def test_initial_draft_has_no_formal_approval_or_backend_write(self):
        task, draft, _ = self.workflow.start(envelope({"type": "user_utterance", "content": REQUEST}))
        self.assertEqual(draft.facts["candidate_id"], "P1")
        self.assertEqual(draft.facts["selected_slot"]["start"][11:16], "14:00")
        self.assertIsNone(draft.confirmation)
        self.assertEqual(draft.allowed_actions, [])
        self.assertEqual(self.writes(), [])
        transcript = self.workflow.transcript(task["task_id"])
        calls = [call["id"] for message in transcript for call in message.get("tool_calls", [])]
        results = [message["tool_call_id"] for message in transcript if message["role"] == "tool"]
        self.assertCountEqual(calls, results)
        self.assertEqual(len(results), len(set(results)))

    def test_unsupported_refinement_revokes_approval_and_does_not_dispatch(self):
        for content in ("改為明天上午", "改星期三", "tomorrow morning", "change to next Wednesday afternoon", "改為下午四點後", "改為2026-10-21下午", "改為婦科", "change to before 3 pm"):
            with self.subTest(content=content):
                self.setUp()
                task, pending, _ = self.start()
                p1 = self.approval(pending)
                before = self.workflow.transcript(task["task_id"])
                calls_before = len(self.pipeline.calls)
                task, paused, _ = self.workflow.handle(task, envelope({"type": "user_utterance", "content": content}))
                self.assertEqual(paused.recovery["reason"], "unsupported_demo_intent")
                self.assertIsNone(paused.confirmation)
                self.assertEqual(len(self.pipeline.calls), calls_before)
                transcript = self.workflow.transcript(task["task_id"])
                self.assertEqual(transcript[:len(before)], before)
                self.assertIn({"role": "user", "content": content}, transcript[len(before):])
                calls = [call["id"] for message in transcript for call in message.get("tool_calls", [])]
                results = [message["tool_call_id"] for message in transcript if message["role"] == "tool"]
                self.assertCountEqual(calls, results)
                self.assertEqual(len(results), len(set(results)))
                with self.assertRaises(ValueError):
                    self.workflow.handle(task, envelope(p1))
                self.assertEqual(self.writes(), [])

    def test_unsupported_initial_intent_never_queries_or_proposes_old_date(self):
        _, paused, _ = self.start("心臟科明天上午")
        self.assertEqual(paused.recovery["reason"], "unsupported_demo_intent")
        self.assertEqual(self.pipeline.calls, [])

    def test_supported_three_pm_forms_select_later_slot(self):
        for text in ("改為下午3點後", "改为下午3点后", "after 3 PM", "下午三點之後", "after 15:00"):
            with self.subTest(text=text):
                self.setUp()
                task, _, _ = self.start()
                task, proposal, _ = self.workflow.handle(task, envelope({"type": "user_utterance", "content": text}))
                self.assertTrue(after_three(text))
                self.assertIsNone(proposal.confirmation)
                self.assertEqual(proposal.facts["selected_slot"]["start"][11:16], "15:30")
                self.assertEqual(proposal.allowed_actions, [])
                self.assertEqual(self.writes(), [])

    def test_browser_snapshot_and_diagnostic_transcript_cannot_change_authoritative_proposal(self):
        task, proposal, _ = self.start()
        task["facts"]["selected_slot"]["id"] = "ATTACKER"
        task["facts"]["slot_id"] = "ATTACKER"
        copy = self.workflow.transcript(task["task_id"])
        next(message for message in copy if message.get("tool_calls"))["tool_calls"][0]["function"]["arguments"] = "{}"
        _, complete, _ = self.workflow.handle(task, envelope(self.approval(proposal)))
        self.assertEqual(complete.receipt["appointment"]["time"], "14:00")
        self.assertEqual(self.writes()[0].arguments["input"]["patient_id"], "PAT-UNIT")
        self.assertTrue(self.writes()[0].arguments["input"]["slot_id"].endswith("-1400"))
        self.assertNotEqual(self.workflow.transcript(task["task_id"])[-2]["tool_calls"][0]["function"]["arguments"], "{}")

    def test_pending_input_and_binding_are_immutable(self):
        task, _, _ = self.start()
        state = self.workflow._states[task["task_id"]]
        proposal = state.proposals[state.pending_id]
        self.assertTrue(proposal.frozen.verify_integrity())
        with self.assertRaises(TypeError):
            proposal.frozen.arguments["input"]["slot_id"] = "ATTACKER"
        with self.assertRaises(TypeError):
            proposal.frozen.arguments["intent_revision"] = 100

    def test_unknown_write_error_blocks_patient_across_tasks(self):
        task, proposal, _ = self.start()
        self.pipeline.write_result = {"code": "NEW_UNCLASSIFIED_FAILURE", "message": "could have committed"}
        _, uncertain, _ = self.workflow.handle(task, envelope(self.approval(proposal)))
        self.assertEqual(uncertain.recovery["reason"], "outcome_needs_checking")
        count = len(self.pipeline.calls)
        _, blocked, _ = self.workflow.start(envelope({"type": "user_utterance", "content": REQUEST}, "S-OTHER"))
        self.assertEqual(blocked.recovery["reason"], "outcome_needs_checking")
        self.assertEqual(len(self.pipeline.calls), count)
        self.assertEqual(len(self.writes()), 1)

    def test_clock_accepts_timestamp_or_clock_object(self):
        self.workflow.clock = lambda: NOW.timestamp()
        _, proposal, _ = self.start()
        self.assertEqual(proposal.confirmation["appointment"]["date"], "2026-10-20")
        self.workflow.clock = lambda: datetime(2026, 10, 13, 9)
        with self.assertRaises(ValueError):
            self.start()

    def test_queued_other_session_cannot_write_after_first_write_becomes_unknown(self):
        task_a, p1, _ = self.start()
        task_b, p2, _ = self.start(session="S-SECOND")
        entered_dispatch = threading.Event()
        release_dispatch = threading.Event()
        queued_second = threading.Event()
        original_dispatch = self.pipeline.dispatch

        class ObservedLock:
            def __init__(self):
                self.lock = threading.Lock()
                self.observer_guard = threading.Lock()
                self.entries = 0

            def __enter__(self):
                with self.observer_guard:
                    self.entries += 1
                    if self.entries == 2:
                        queued_second.set()
                self.lock.acquire()

            def __exit__(self, *unused):
                self.lock.release()

        def gate_dispatch(call):
            if call.name == "medical.create_registration":
                entered_dispatch.set()
                if not release_dispatch.wait(5):
                    raise AssertionError("write gate was not released")
            return original_dispatch(call)

        self.workflow._patient_mutation_lock = ObservedLock()
        self.pipeline.write_result = {"code": "MCP_TIMEOUT", "status": 504}
        self.pipeline.dispatch = gate_dispatch
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(self.workflow.handle, task_a, envelope(self.approval(p1)))
            try:
                self.assertTrue(entered_dispatch.wait(5))
                second = workers.submit(self.workflow.handle, task_b, envelope(self.approval(p2), "S-SECOND"))
                self.assertTrue(queued_second.wait(5))
            finally:
                release_dispatch.set()
            for future in (first, second):
                _, result, _ = future.result(timeout=5)
                self.assertEqual(result.recovery["reason"], "outcome_needs_checking")
                self.assertIsNone(result.receipt)
        self.assertEqual(len(self.writes()), 1)


if __name__ == "__main__":
    unittest.main()
