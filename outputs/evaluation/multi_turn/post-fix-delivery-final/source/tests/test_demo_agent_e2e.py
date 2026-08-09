"""Scripted-model acceptance over real HTTP, MCP stdio and isolated JSON data.

Only the model is scripted. Fault tests explicitly lose or alter a successful
MCP reply *after* the real backend has committed, so they exercise uncertainty
without pretending to prove external exactly-once or crash recovery.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from middleware.intent import KeywordIntentRecognizer
from middleware.interaction_voice import CoreVoiceTurnProvider
from middleware.mcp_client import McpClientError
from middleware.server import create_application, create_http_server
from middleware.voice import VoiceProviderSettings
from mock_backends.core.clock import FixedClock, MACAU_TZ
from mock_backends.core.persistence import JsonLinesTextRepository
from mock_backends.server import create_application as create_backend_application
from mock_backends.server import make_request_handler


PATIENT = "PAT-DEMO-AGENT-E2E"
SLOT_1400 = "SLOT-DEMO-REG-20261020-CARDIO-1400"
SLOT_1530 = "SLOT-DEMO-REG-20261020-CARDIO-1530"
REQUEST = "我想預約心臟科，下週二下午。"
CHANGE = "改為下午3點後。"
ALLOWLIST = {
    "medical.list_departments",
    "medical.search_registration_slots",
    "medical.create_registration",
    "medical.get_my_appointments",
}


def native_call(call_id, name, arguments):
    return {"choices": [{"message": {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)},
        }],
    }}]}


def search_call(call_id="call-search-1"):
    return native_call(call_id, "medical.search_registration_slots", {
        "department_id": "DEPT-CARDIO", "date": "2026-10-20", "session": "afternoon",
    })


def proposal_call(slot_id=SLOT_1400, call_id="call-P1"):
    return native_call(call_id, "medical.create_registration", {
        "patient_id": PATIENT, "department_id": "DEPT-CARDIO",
        "doctor_id": "DOC-002", "slot_id": slot_id, "consent": True,
    })


def control(action, **fields):
    # Explicit test model decisions follow the runtime's typed control contract.
    if action == "select_slot" and "target" not in fields:
        fields["target"] = {"kind": "current"}
    if action == "update_constraints" and "after_three" in fields:
        fields["time_constraint"] = ({"kind": "lower_bound", "time": "15:00", "inclusive": False}
                                     if fields.pop("after_three") else {"kind": "afternoon"})
    return {"action": action, **fields}


def first_proposal_script():
    return [
        native_call("call-departments-1", "medical.list_departments", {
            "keyword": "Cardiology", "active_only": True,
        }),
        search_call(),
        proposal_call(),
    ]


class QueuedModel:
    """Native call IDs and full prompt snapshots are observable test evidence."""

    mode = "scripted"

    def __init__(self):
        self.responses = []
        self.requests = []
        self.lock = threading.Lock()
        self.block_call_id = None
        self.block_action = None
        self.entered = threading.Event()
        self.release = threading.Event()

    def add(self, *responses):
        with self.lock:
            self.responses.extend(deepcopy(responses))

    def complete(self, messages, **options):
        with self.lock:
            self.requests.append((deepcopy(messages), deepcopy(options)))
            if not self.responses:
                raise AssertionError("Unexpected extra model decision")
            result = self.responses.pop(0)
        calls = result.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
        if (calls and calls[0].get("id") == self.block_call_id) or (self.block_action and result.get("action") == self.block_action):
            self.entered.set()
            if not self.release.wait(8):
                raise AssertionError("Model decision test gate was not released")
        return result


class CapturingRouter:
    """Observe actual HTTP backend requests without replacing tool execution."""

    def __init__(self, router):
        self.router = router
        self.requests = []
        self.responses = []
        self.lock = threading.Lock()
        self.block_registration = False
        self.entered = threading.Event()
        self.release = threading.Event()

    def dispatch(self, request):
        with self.lock:
            self.requests.append(deepcopy(request))
        if self.block_registration and request.method == "POST" and request.path.endswith("/registrations"):
            self.entered.set()
            if not self.release.wait(8):
                raise AssertionError("Backend booking test gate was not released")
        response = self.router.dispatch(request)
        with self.lock:
            self.responses.append((deepcopy(request), deepcopy(response)))
        return response


class DemoAgentEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.data_dir = Path(self.tempdir.name)
        self.clock = FixedClock(datetime(2026, 10, 13, 9, tzinfo=MACAU_TZ))
        self.router = CapturingRouter(create_backend_application(self.data_dir, clock=self.clock))
        self.backend = ThreadingHTTPServer(("127.0.0.1", 0), make_request_handler(self.router))
        self.backend_thread = threading.Thread(target=self.backend.serve_forever, daemon=True)
        self.backend_thread.start()
        self.addCleanup(self.stop_server, self.backend, self.backend_thread)
        self.model = QueuedModel()
        self.app = create_application(
            f"http://127.0.0.1:{self.backend.server_port}", PATIENT, "Bearer mock-user-token",
            intent_recognizer=KeywordIntentRecognizer(),
            demo_agent_mode="scripted", demo_model_client=self.model, demo_clock=self.clock,
        )
        self.addCleanup(self.app.close)
        self.middleware = create_http_server("127.0.0.1", 0, self.app)
        self.middleware_thread = threading.Thread(target=self.middleware.serve_forever, daemon=True)
        self.middleware_thread.start()
        self.addCleanup(self.stop_server, self.middleware, self.middleware_thread)
        self.interaction_number = 0
        self.counter_lock = threading.Lock()
        self.session_id = "S-DEMO-E2E"

    @staticmethod
    def stop_server(server, thread):
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    def http_json(self, method, url, body=None, headers=None):
        request = Request(
            url, method=method,
            data=None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        opener = build_opener(ProxyHandler({}))
        try:
            with opener.open(request, timeout=15) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            try:
                return error.code, json.loads(error.read())
            finally:
                error.close()

    def interact(self, event, *, session_id=None, allow_rejection=False, audit=None):
        with self.counter_lock:
            self.interaction_number += 1
            number = self.interaction_number
        status, result = self.http_json("POST", f"http://127.0.0.1:{self.middleware.server_port}/api/interactions", {
            "routing": {"session_id": session_id or self.session_id, "interaction_id": f"INT-DEMO-{number}"},
            "event": deepcopy(event), "audit": audit or {"source": "text"},
        })
        if allow_rejection:
            self.assertIn(status, (200, 400, 403, 409, 422), result)
        else:
            self.assertEqual(status, 200, result)
        return result

    def say(self, text, **kwargs):
        if text == CHANGE and not self.app.demo_workflow._patient_blocked():
            with self.model.lock:
                self.model.responses.insert(0, control("update_constraints", after_three=True))
        return self.interact({"type": "user_utterance", "task_id": None, "content": text}, **kwargs)

    def p1(self):
        self.model.add(*first_proposal_script())
        result = self.say(REQUEST)
        self.assertEqual(result["task"]["type"], "medical_demo_agent")
        self.assertEqual(result["task"]["status"], "awaiting_input")
        self.assertFalse(any(a["event"].get("decision") == "approve" for a in result["workspace"]["actions"]))
        self.model.add(control("select_slot"))
        result = self.say("就14:00嗰個")
        self.assertEqual(result["task"]["status"], "awaiting_confirmation")
        self.assertIn("14:00", json.dumps(result, ensure_ascii=False))
        self.assertIsNone(result["receipt"])
        self.assertEqual(self.booking_requests(), [])
        return result

    def p2(self):
        p1 = self.p1()
        self.model.add(search_call("call-search-2"), proposal_call(SLOT_1530, "call-P2"))
        p2 = self.say(CHANGE)
        self.assertEqual(p2["task"]["status"], "awaiting_input")
        self.model.add(control("select_slot"))
        p2 = self.say("就15:30嗰個")
        self.assertEqual(p2["task"]["status"], "awaiting_confirmation")
        self.assertIn("15:30", json.dumps(p2, ensure_ascii=False))
        self.assertNotEqual(self.approval(p1)["confirmation_id"], self.approval(p2)["confirmation_id"])
        self.assertEqual(self.booking_requests(), [])
        return p1, p2

    @staticmethod
    def approval(result):
        return next(action["event"] for action in result["workspace"]["actions"]
                    if action["event"].get("decision") == "approve")

    def booking_requests(self, patient_id=PATIENT):
        with self.router.lock:
            return [request for request in self.router.requests
                    if request.method == "POST" and request.path.endswith("/registrations")
                    and request.header("X-Patient-Id") == patient_id]

    def appointments(self):
        return JsonLinesTextRepository(self.data_dir / "medical" / "appointments.txt").list()

    def transcript(self, result):
        return self.app.demo_workflow.transcript(result["task"]["task_id"])

    def assert_pairing(self, transcript, *, pending=None):
        """Every issued ID has one result; only the pending proposal may lack it."""
        issued, results = {}, {}
        for index, message in enumerate(transcript):
            if message["role"] == "assistant":
                for call in message.get("tool_calls", []):
                    self.assertNotIn(call["id"], issued)
                    issued[call["id"]] = index
            elif message["role"] == "tool":
                call_id = message["tool_call_id"]
                self.assertIn(call_id, issued)
                self.assertNotIn(call_id, results)
                self.assertLess(issued[call_id], index)
                results[call_id] = index
        self.assertEqual(set(issued) - set(results), {pending} if pending else set())
        return issued, results

    def assert_booked(self, result, slot_id=SLOT_1530, time="15:30"):
        self.assertEqual(result["task"]["status"], "completed")
        self.assertEqual(result["workspace"]["view"], "appointment_completed")
        receipt = result["receipt"]
        self.assertRegex(receipt["receipt_id"], r"^MED-REG-\d+$")
        records = [item for item in self.appointments() if item.get("patient_id") == PATIENT]
        self.assertEqual(len(records), 1)
        appointment = records[0]
        self.assertEqual(appointment["status"], "booked")
        self.assertEqual(appointment["patient"]["id"], PATIENT)
        self.assertEqual(appointment["department"]["id"], "DEPT-CARDIO")
        self.assertEqual(appointment["slot_id"], slot_id)
        self.assertEqual(appointment["start"], f"2026-10-20T{time}:00+08:00")
        backend_task = JsonLinesTextRepository(self.data_dir / "medical" / "tasks.txt").get(appointment["task_id"])
        self.assertEqual(backend_task["status"], "completed")
        self.assertEqual(backend_task["appointment_id"], appointment["id"])
        responses = [response for request, response in self.router.responses
                     if request.method == "POST" and request.path.endswith("/registrations")
                     and request.header("X-Patient-Id") == PATIENT and response.status == 201]
        self.assertEqual(receipt["receipt_id"], responses[0].body["receipt"]["reference"])
        self.assertIn(time, json.dumps(result, ensure_ascii=False))
        self.assertIn("2026-10-20", json.dumps(result, ensure_ascii=False))
        self.assertIn("第一門診", json.dumps(result, ensure_ascii=False))
        self.assert_pairing(self.transcript(result))

    def test_primary_story_pairs_superseded_p1_and_books_p2_once(self):
        p1, p2 = self.p2()
        transcript = self.transcript(p2)
        issued, results = self.assert_pairing(transcript, pending=None)
        superseded = transcript[results["call-P1"]]
        self.assertIn("DRAFT_ONLY", superseded["content"])
        change_index = next(index for index, item in enumerate(transcript)
                            if item["role"] == "user" and item["content"] == CHANGE)
        self.assertLess(results["call-P1"], change_index)
        self.assertLess(issued["call-P1"], results["call-P1"])
        self.assertGreater(p2["task"]["facts"]["intent_revision"], p1["task"]["facts"]["intent_revision"])

        stale = self.interact(self.approval(p1), allow_rejection=True)
        self.assertIsNone(stale.get("receipt"))
        self.assertEqual(self.booking_requests(), [])
        approved = self.interact(self.approval(p2))
        self.assert_booked(approved)
        repeated = self.interact(self.approval(p2))
        self.assertEqual(repeated["receipt"], approved["receipt"])
        self.assertEqual(len(self.booking_requests()), 1)
        request = self.booking_requests()[0]
        self.assertTrue(request.header("Idempotency-Key"))
        self.assertEqual(request.header("Authorization"), "Bearer mock-user-token")
        self.assertEqual(request.body["patient_id"], PATIENT)
        self.assertEqual(request.body["slot_id"], SLOT_1530)
        self.assertIsNotNone(self.app.mcp_client.process)
        self.assertIsNone(self.app.mcp_client.process.poll())
        self.assertEqual(self.app.mcp_client.process.args[1:3], ["-m", "MCP"])
        for _, options in self.model.requests:
            if options.get("demo_control"):
                self.assertEqual(options["tools"], [])
                self.assertEqual(options["tool_choice"], "none")
                continue
            self.assertEqual({item["function"]["name"] for item in options["tools"]}, ALLOWLIST)
            self.assertTrue(all("context" not in item["function"]["parameters"].get("properties", {})
                                for item in options["tools"]))

    def test_concurrent_p2_approvals_have_one_write_and_one_receipt(self):
        _, p2 = self.p2()
        gate = threading.Barrier(4)
        def approve():
            gate.wait(timeout=5)
            return self.interact(self.approval(p2))
        with ThreadPoolExecutor(max_workers=4) as workers:
            results = list(workers.map(lambda _: approve(), range(4)))
        self.assert_booked(results[0])
        self.assertTrue(all(item["receipt"] == results[0]["receipt"] for item in results))
        self.assertEqual(len(self.booking_requests()), 1)

    def test_intent_change_winning_lock_invalidates_queued_old_approval(self):
        p1 = self.p1()
        self.model.add(search_call("call-search-2"), proposal_call(SLOT_1530, "call-P2"))
        self.model.block_call_id = "call-search-2"
        with ThreadPoolExecutor(max_workers=2) as workers:
            change = workers.submit(self.say, CHANGE)
            self.assertTrue(self.model.entered.wait(5))
            approval = workers.submit(self.interact, self.approval(p1), allow_rejection=True)
            self.model.release.set()
            p2 = change.result(timeout=10)
            stale = approval.result(timeout=10)
        self.assertEqual(p2["task"]["status"], "awaiting_input")
        self.assertIsNone(stale.get("receipt"))
        self.assertEqual(self.booking_requests(), [])
        self.assert_pairing(self.transcript(p2), pending=None)

    def test_approval_winning_lock_finishes_before_later_change(self):
        p1 = self.p1()
        self.router.block_registration = True
        with ThreadPoolExecutor(max_workers=2) as workers:
            approval = workers.submit(self.interact, self.approval(p1))
            self.assertTrue(self.router.entered.wait(5))
            change = workers.submit(self.say, CHANGE)
            self.router.release.set()
            completed = approval.result(timeout=10)
            late = change.result(timeout=10)
        self.assert_booked(completed, SLOT_1400, "14:00")
        self.assertEqual(late["task"]["task_id"], completed["task"]["task_id"])
        self.assertEqual(late["task"]["status"], "completed")
        self.assertEqual(late["receipt"], completed["receipt"])
        self.assertTrue(late["task"]["facts"].get("late_change_message"))
        self.assertEqual(len(self.booking_requests()), 1)

    def test_voice_yes_is_not_approval_and_transcription_uses_same_task(self):
        self.model.add(*first_proposal_script())
        provider = CoreVoiceTurnProvider(
            self.app.interaction_core, self.app.delivery_orchestrator,
            stt=object(), settings=VoiceProviderSettings(),
        )
        first = provider.handle_transcript(self.session_id, REQUEST).metadata
        self.assertEqual(first["task"]["type"], "medical_demo_agent")
        self.assertEqual(first["task"]["status"], "awaiting_input")
        self.model.add(control("clarify", message="請選定時段。"))
        spoken_yes = provider.handle_transcript(self.session_id, "yes，確認掛號").metadata
        self.assertEqual(spoken_yes["task"]["task_id"], first["task"]["task_id"])
        self.assertNotEqual(spoken_yes["task"]["status"], "completed")
        self.assertIsNone(spoken_yes["receipt"])
        self.assertEqual(self.booking_requests(), [])
        self.assertEqual(len(self.model.requests), 4)
        self.model.add(control("select_slot"))
        selected = self.say("就14:00嗰個")
        confirmed = self.interact(self.approval(selected))
        self.assert_booked(confirmed, SLOT_1400, "14:00")

    def test_forged_or_cross_session_action_cannot_authorize(self):
        p1 = self.p1()
        action = self.approval(p1)
        for field in ("action_id", "confirmation_id", "task_id"):
            with self.subTest(field=field):
                tampered = {**action, field: "UNISSUED"}
                result = self.interact(tampered, allow_rejection=True)
                self.assertIsNone(result.get("receipt"))
                self.assertEqual(self.booking_requests(), [])
        other = self.interact(action, session_id="S-OTHER", allow_rejection=True)
        self.assertIsNone(other.get("receipt"))
        self.assertEqual(self.booking_requests(), [])

    def test_expired_proposal_cannot_dispatch(self):
        p1 = self.p1()
        self.clock._value += timedelta(minutes=6)
        result = self.interact(self.approval(p1), allow_rejection=True)
        self.assertIsNone(result.get("receipt"))
        self.assertEqual(self.booking_requests(), [])

    def test_action_cannot_replace_frozen_final_input(self):
        p1 = self.p1()
        event = {**self.approval(p1), "input": {"patient_id": "ATTACKER", "slot_id": SLOT_1530},
                 "slot_id": SLOT_1530, "patient_id": "ATTACKER", "idempotency_key": "ATTACKER-KEY"}
        result = self.interact(event, allow_rejection=True)
        requests = self.booking_requests()
        if requests:
            self.assertEqual(requests[0].body["slot_id"], SLOT_1400)
            self.assertEqual(requests[0].body["patient_id"], PATIENT)
            self.assertNotEqual(requests[0].header("Idempotency-Key"), "ATTACKER-KEY")
            self.assert_booked(result, SLOT_1400, "14:00")
        else:
            self.assertIsNone(result.get("receipt"))

    def test_slot_loss_reproposes_available_slot_with_new_confirmation(self):
        p1 = self.p1()
        status, external = self.http_json("POST", f"http://127.0.0.1:{self.backend.server_port}/mock/medical/v1/registrations", {
            "patient_id": "PAT-OTHER", "department_id": "DEPT-CARDIO", "doctor_id": "DOC-002",
            "slot_id": SLOT_1400, "consent": True,
        }, {"Authorization": "Bearer mock-user-token", "X-Patient-Id": "PAT-OTHER", "Idempotency-Key": "EXTERNAL-SLOT-LOSS"})
        self.assertEqual(status, 201, external)
        self.model.add(search_call("call-search-recovery"), proposal_call(SLOT_1530, "call-replacement"))
        replacement = self.interact(self.approval(p1))
        self.assertEqual(replacement["task"]["status"], "awaiting_input")
        self.model.add(control("select_slot"))
        replacement = self.say("就15:30嗰個")
        self.assertIsNone(replacement["receipt"])
        self.assertNotEqual(self.approval(replacement)["confirmation_id"], self.approval(p1)["confirmation_id"])
        self.assertEqual(len(self.booking_requests()), 1)
        self.assertEqual([item for item in self.appointments() if item.get("patient_id") == PATIENT], [])
        self.assertIn("SLOT_NOT_AVAILABLE", json.dumps(self.transcript(replacement)))
        booked = self.interact(self.approval(replacement))
        self.assert_booked(booked)
        self.assertEqual(len(self.booking_requests()), 2)
        self.assertNotEqual(self.booking_requests()[0].header("Idempotency-Key"), self.booking_requests()[1].header("Idempotency-Key"))

    def test_multiple_model_calls_execute_neither(self):
        first = first_proposal_script()[0]
        first["choices"][0]["message"]["tool_calls"].extend(search_call()["choices"][0]["message"]["tool_calls"])
        self.model.add(first)
        result = self.say(REQUEST)
        self.assertIsNone(result["receipt"])
        self.assertNotEqual(result["task"]["status"], "completed")
        self.assertTrue(result["recovery"])
        self.assertEqual(self.router.requests, [])

    def test_unsupported_model_tool_executes_nothing(self):
        self.model.add(native_call("bad-tool", "medical.create_appointment", {"consent": True}))
        result = self.say(REQUEST)
        self.assertIsNone(result["receipt"])
        self.assertTrue(result["recovery"])
        self.assertEqual(self.router.requests, [])

    def test_invented_after_time_parameter_is_rejected_before_search(self):
        self.model.add(native_call("invented-parameter", "medical.search_registration_slots", {
            "department_id": "DEPT-CARDIO", "date": "2026-10-20",
            "session": "afternoon", "after_time": "15:00",
        }))
        result = self.say(REQUEST)
        self.assertTrue(result["recovery"])
        self.assertEqual(self.router.requests, [])

    def test_changed_preference_rejects_model_selection_before_three(self):
        p1 = self.p1()
        self.model.add(search_call("call-search-bad-change"), proposal_call(SLOT_1400, "call-bad-P2"))
        result = self.say(CHANGE)
        self.assertIsNone(result["receipt"])
        self.assertTrue(result["recovery"])
        self.assertEqual(self.booking_requests(), [])
        self.interact(self.approval(p1), allow_rejection=True)
        self.assertEqual(self.booking_requests(), [])

    def test_model_claim_of_success_is_not_a_verified_receipt(self):
        self.model.add({"action": "respond", "message": "掛號已成功，MED-REG-FAKE。"})
        result = self.say(REQUEST)
        self.assertNotEqual(result["task"]["status"], "completed")
        self.assertIsNone(result["receipt"])
        self.assertNotIn("MED-REG-FAKE", result["response"]["display_text"])
        self.assertEqual(self.booking_requests(), [])

    def test_step_limit_pauses_without_write(self):
        self.model.add(*(native_call(f"list-{index}", "medical.list_departments", {
            "keyword": "Cardiology", "active_only": True,
        }) for index in range(6)))
        result = self.say(REQUEST)
        self.assertEqual(len(self.model.requests), 4)
        self.assertEqual(len(self.router.requests), 4)
        self.assertIsNone(result["receipt"])
        self.assertTrue(result["recovery"])
        self.assertEqual(self.booking_requests(), [])

    def test_lost_successful_write_reply_blocks_patient_without_retry_or_new_key(self):
        p1 = self.p1()
        original_call = self.app.mcp_client.call_tool
        def lose_reply(name, arguments):
            result = original_call(name, arguments)
            if name == "medical.create_registration":
                raise McpClientError("MCP_TIMEOUT", "Injected lost committed reply", status=504, retryable=True)
            return result
        self.app.mcp_client.call_tool = lose_reply
        uncertain = self.interact(self.approval(p1))
        self.assert_uncertain(uncertain)
        self.assertEqual(len(self.appointments()), 1, "The fault loses a reply after the real booking")
        self.assertEqual(len(self.booking_requests()), 1)
        for result in (
            self.interact(self.approval(p1), allow_rejection=True),
            self.say(CHANGE),
            self.say(REQUEST, session_id="S-PATIENT-SECOND-SESSION"),
        ):
            self.assertIsNone(result.get("receipt"))
        self.assertEqual(len(self.booking_requests()), 1)
        self.assertEqual(len(self.model.requests), 4)
        self.assert_pairing(self.transcript(uncertain))

    def test_patient_block_serializes_two_sessions_across_lost_write_reply(self):
        first = self.p1()
        other_session = "S-SAME-PATIENT-SECOND"
        self.model.add(*first_proposal_script())
        second = self.say(REQUEST, session_id=other_session)
        self.model.add(control("select_slot"))
        second = self.say("就14:00嗰個", session_id=other_session)
        self.assertEqual(second["task"]["status"], "awaiting_confirmation")
        self.assertNotEqual(first["task"]["task_id"], second["task"]["task_id"])

        committed_reply = threading.Event()
        release_reply = threading.Event()
        other_confirmation_entered = threading.Event()
        first_key = []
        original_call = self.app.mcp_client.call_tool
        original_handle = self.app.demo_workflow.handle

        def lose_first_reply(name, arguments):
            result = original_call(name, arguments)
            if name == "medical.create_registration" and not committed_reply.is_set():
                first_key.append(arguments["context"]["idempotency_key"])
                committed_reply.set()
                if not release_reply.wait(8):
                    raise AssertionError("Lost-reply race gate was not released")
                raise McpClientError("MCP_TIMEOUT", "Injected lost committed reply", status=504, retryable=True)
            return result

        def observe_other_confirmation(task, envelope):
            if envelope.session_id == other_session and envelope.event.get("decision") == "approve":
                other_confirmation_entered.set()
            return original_handle(task, envelope)

        self.app.mcp_client.call_tool = lose_first_reply
        self.app.demo_workflow.handle = observe_other_confirmation
        with ThreadPoolExecutor(max_workers=2) as workers:
            first_approval = workers.submit(self.interact, self.approval(first))
            try:
                self.assertTrue(committed_reply.wait(5), "First session must really commit before its reply is lost")
                second_approval = workers.submit(self.interact, self.approval(second), session_id=other_session)
                self.assertTrue(other_confirmation_entered.wait(5), "Other session must reach the workflow while the first outcome is unresolved")
                self.assertFalse(second_approval.done(), "Other session must wait for patient outcome classification")
                self.assertEqual(len(self.booking_requests()), 1)
            finally:
                release_reply.set()
            uncertain_first = first_approval.result(timeout=10)
            uncertain_second = second_approval.result(timeout=10)

        self.assert_uncertain(uncertain_first)
        self.assert_uncertain(uncertain_second)
        self.assertEqual(len(self.booking_requests()), 1)
        self.assertEqual(self.booking_requests()[0].header("Idempotency-Key"), first_key[0])
        self.assertEqual(len(self.appointments()), 1)
        self.assertEqual(len(self.model.requests), 8)
        self.assert_pairing(self.transcript(uncertain_first))
        self.assert_pairing(self.transcript(uncertain_second))

    def assert_uncertain(self, result):
        self.assertIsNone(result["receipt"])
        self.assertNotEqual(result["task"]["status"], "completed")
        self.assertEqual(result["recovery"]["reason"], "outcome_needs_checking")
        self.assertTrue(result["recovery"].get("message"))
        self.assertNotIn("預約已完成", result["response"]["display_text"])

    def test_legacy_query_and_cash_paths_keep_original_engine(self):
        query = self.say("我想查詢自己的醫療預約")
        self.assertEqual(query["task"]["type"], "medical_appointment")
        self.assertEqual(query["workspace"]["view"], "appointment_list")
        cash = self.say("我想查現金分享計劃", session_id="S-CASH")
        self.assertEqual(cash["task"]["type"], "cash_sharing_query")
        self.assertEqual(cash["workspace"]["view"], "cash_sharing_summary")
        self.assertEqual(self.model.requests, [])

    def test_existing_examination_task_keeps_legacy_engine(self):
        legacy = self.say("我想預約醫療服務")
        self.assertEqual(legacy["task"]["type"], "medical_appointment")
        continued = self.say(REQUEST)
        self.assertEqual(continued["task"]["task_id"], legacy["task"]["task_id"])
        self.assertEqual(continued["task"]["type"], "medical_appointment")
        self.assertEqual(self.model.requests, [])

    def test_completed_demo_can_start_legacy_query_and_examination(self):
        p1 = self.p1()
        completed = self.interact(self.approval(p1))
        self.assert_booked(completed, SLOT_1400, "14:00")
        query = self.say("我想查詢自己的醫療預約")
        self.assertEqual(query["task"]["type"], "medical_appointment")
        self.assertNotEqual(query["task"]["task_id"], completed["task"]["task_id"])
        self.assertEqual(query["workspace"]["view"], "appointment_list")
        examination = self.say("我想預約醫療檢查服務")
        self.assertEqual(examination["task"]["type"], "medical_appointment")
        self.assertEqual(len(self.model.requests), 4)
        self.assertEqual(len(self.booking_requests()), 1)


def _corrupt_receipt_test(field):
    def test(self):
        p1 = self.p1()
        original_call = self.app.mcp_client.call_tool
        def corrupt_reply(name, arguments):
            payload = original_call(name, arguments)
            if name != "medical.create_registration":
                return payload
            payload = deepcopy(payload)
            if field == "patient_id":
                payload["data"]["patient_id"] = "PAT-OTHER"
            elif field == "patient_record":
                payload["data"]["patient"]["id"] = "PAT-OTHER"
            elif field == "department":
                payload["data"]["department"]["id"] = "DEPT-OTHER"
            elif field == "slot":
                payload["data"]["slot_id"] = SLOT_1530
            elif field == "start":
                payload["data"]["start"] = "2026-10-20T15:30:00+08:00"
            elif field == "status":
                payload["data"]["status"] = "cancelled"
            elif field == "backend_task":
                payload["task"]["status"] = "in-progress"
            elif field == "receipt":
                payload["receipt"]["reference"] = "MED-APT-FAKE"
            return payload
        self.app.mcp_client.call_tool = corrupt_reply
        result = self.interact(self.approval(p1))
        self.assert_uncertain(result)
        self.assertEqual(len(self.booking_requests()), 1)
        self.assertEqual(len(self.appointments()), 1)
        self.assert_pairing(self.transcript(result))
    test.__doc__ = f"A real committed booking with mismatched {field} never displays success."
    return test


for _field in ("patient_id", "patient_record", "department", "slot", "start", "status", "backend_task", "receipt"):
    setattr(DemoAgentEndToEndTests, f"test_unverified_{_field}_never_claims_success", _corrupt_receipt_test(_field))


if __name__ == "__main__":
    unittest.main()
