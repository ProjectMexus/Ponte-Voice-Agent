"""Scripted LLM -> canonical HTTP -> actual MCP stdio -> persistent mock backend."""
import copy
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from urllib.request import Request, ProxyHandler, build_opener

from middleware.server import create_application, create_http_server
from middleware.llm_transport import OpenAICompatibleChatClient
from middleware.tests.test_agent_orchestrator import ScriptedModel, tool
from mock_backends.core.clock import FixedClock, MACAU_TZ
from mock_backends.server import create_http_server as backend_server
from tests.scripted_llm_http import ScriptedChatEndpoint


class AgentFullStackTests(unittest.TestCase):
    def test_approval_executes_once_and_resumes_through_real_mcp(self):
        self._booking_flow()

    def test_real_llm_http_transport_mcp_backend_approval_and_resume(self):
        self._booking_flow(llm_http=True)

    def _booking_flow(self, llm_http=False):
        with tempfile.TemporaryDirectory() as directory:
            backend = backend_server("127.0.0.1", 0, Path(directory), clock=FixedClock(datetime(2026, 8, 3, 9, tzinfo=MACAU_TZ)))
            backend_thread = threading.Thread(target=backend.serve_forever, daemon=True)
            backend_thread.start()
            opener = build_opener(ProxyHandler({}))

            def post(url, body, headers=None):
                request = Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **(headers or {})})
                with opener.open(request, timeout=10) as response:
                    return json.load(response)

            app = middleware = None
            middleware_thread = None
            provider = None
            try:
                # Establish a genuine patient referral appointment, rather than accepting
                # a fabricated model-provided reference as proof of a prerequisite.
                referral = post(f"http://127.0.0.1:{backend.server_port}/mock/medical/v1/registrations",
                    {"patient_id": "PAT-DEMO-001", "department_id": "DEPT-CARDIO", "slot_id": "SLOT-REG-20260812-CARDIO-1030", "consent": True},
                    {"Authorization": "Bearer mock-user-token", "X-Patient-Id": "PAT-DEMO-001", "Idempotency-Key": "SEED-REFERRAL"})
                model = ScriptedModel([
                    tool("medical.list_appointment_services"),
                    tool("medical.search_appointment_slots", service_id="SERVICE-US-001", date_from="2026-08-12", date_to="2026-08-12"),
                    tool("medical.get_my_appointments"),
                    tool("medical.create_appointment", service_id="SERVICE-US-001", slot_id="SLOT-US-20260812-1400", referring_appointment_id=referral["data"]["id"]),
                    tool("medical.get_my_appointments"),
                    {"action": "respond", "message": "The approved appointment is recorded in your appointment list."},
                ])
                client = model
                if llm_http:
                    provider = ScriptedChatEndpoint(model)
                    client = OpenAICompatibleChatClient(provider.url, model="scripted-fixture")
                app = create_application(f"http://127.0.0.1:{backend.server_port}", "PAT-DEMO-001", "Bearer mock-user-token", agent_enabled=True, agent_client=client)
                middleware = create_http_server("127.0.0.1", 0, app)
                middleware_thread = threading.Thread(target=middleware.serve_forever, daemon=True)
                middleware_thread.start()

                def interact(event, interaction_id):
                    return post(f"http://127.0.0.1:{middleware.server_port}/api/interactions",
                        {"routing": {"session_id": "AGENT-REAL", "interaction_id": interaction_id}, "event": event})

                pending = interact({"type": "user_utterance", "content": "Book the ultrasound after checking my referral."}, "START")
                self.assertEqual(pending["task"]["status"], "awaiting_confirmation")
                before = [json.loads(line) for line in (Path(directory) / "medical" / "appointments.txt").read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(before), 1)
                approve = next(a["event"] for a in pending["workspace"]["actions"] if a["event"].get("decision") == "approve")
                done = interact(approve, "APPROVE")
                self.assertEqual(done["task"]["status"], "completed")
                self.assertEqual(done["receipt"]["appointment"]["service"], "腹部超聲波檢查")
                self.assertEqual(interact(approve, "REPLAY")["receipt"], done["receipt"])
                appointments = [json.loads(line) for line in (Path(directory) / "medical" / "appointments.txt").read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(appointments), 2)
                self.assertEqual(sum(a["slot_id"] == "SLOT-US-20260812-1400" for a in appointments), 1)
                run = app.sessions.get_or_create("AGENT-REAL").agent_execution
                self.assertEqual(sum(m["role"] == "tool" for m in model.requests[-1][0]), 5)
                self.assertEqual(len(model.requests), 6)
                self.assertIsNone(app.mcp_client.process.poll())
                self.assertNotIn("mock-user-token", json.dumps(run.trace))
                if provider:
                    self.assertEqual(provider.protocol_errors, [])
                # Optional artifact is generated from this successful runtime, never a
                # hand-written sample or hidden chain-of-thought.
                trace_path = os.environ.get("PONTE_TEST_TRACE_PATH")
                if trace_path and llm_http:
                    Path(trace_path).write_text(json.dumps({"source": "test_agent_full_stack.py", "transport": "HTTP /api/interactions -> real chat HTTP client -> scripted provider HTTP -> MCP stdio -> mock backend", "model_decisions": model.decisions, "trace": run.trace,
                        "proposal": pending["confirmation"], "approval_event": approve, "receipt": done["receipt"],
                        "backend_evidence": {"appointment_count_before": 1, "appointment_count_after_approval_and_replay": 2, "matching_booking_count": 1},
                        "last_model_history_roles": [m["role"] for m in model.requests[-1][0]]}, ensure_ascii=False, indent=2), encoding="utf-8")
            finally:
                if middleware:
                    middleware.shutdown()
                    middleware.server_close()
                    middleware_thread.join(2)
                elif app:
                    app.close()
                backend.shutdown()
                backend.server_close()
                backend_thread.join(2)
                if provider:
                    provider.close()

