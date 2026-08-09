"""Exercise actual chat HTTP request/response transport through canonical HTTP."""
import json
import threading
import unittest
from urllib.request import ProxyHandler, build_opener

from middleware.llm_transport import OpenAICompatibleChatClient
from middleware.server import create_application, create_http_server
from middleware.tests import test_agent_orchestrator as http_fixture
from middleware.tests.test_agent_orchestrator import FakeMcp, ScriptedModel, tool
from tests.scripted_llm_http import ScriptedChatEndpoint


class AgentProviderHttpTests(unittest.TestCase):
    post = http_fixture.AgentHttpTests.post
    utter = http_fixture.AgentHttpTests.utter
    propose = http_fixture.AgentHttpTests.propose
    action = staticmethod(http_fixture.AgentHttpTests.action)

    def setUp(self):
        self.model = ScriptedModel([])
        self.provider = ScriptedChatEndpoint(self.model)
        self.mcp = FakeMcp()
        client = OpenAICompatibleChatClient(self.provider.url, model="scripted-fixture", api_key="test-provider-secret")
        self.app = create_application("http://127.0.0.1:8080", "PAT-1", "Bearer server-secret", mcp_client=self.mcp, agent_enabled=True, agent_client=client)
        self.server = create_http_server("127.0.0.1", 0, self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.opener = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.provider.close()
        self.assertEqual(self.provider.protocol_errors, [])

    def test_real_chat_http_transport_native_tools_approval_and_resume(self):
        pending = self.propose()
        self.model.responses = [tool("medical.get_my_appointments"), {"action": "respond", "message": "Recorded."}]
        status, done = self.post(self.action(pending), interaction="APPROVED")
        self.assertEqual(status, 200)
        self.assertIsNotNone(done["receipt"])
        self.assertEqual(done["task"]["status"], "completed")
        self.assertEqual(self.provider.header_keys, ["Bearer test-provider-secret"] * 5)
        self.assertNotIn("server-secret", json.dumps(self.model.requests))

    def test_http_503_and_invalid_json_pause_without_dispatch_and_can_resume(self):
        for index, response in enumerate((RuntimeError("unavailable"), b"not json")):
            session = f"FAIL-{index}"
            self.model.responses = [response]
            status, failed = self.utter(session=session, interaction="START")
            self.assertEqual(status, 200)
            self.assertEqual(failed["recovery"]["reason"], "MODEL_FAILURE")
            self.assertNotIn("test-provider-secret", json.dumps(failed))
            self.assertEqual(self.mcp.calls, [])
            self.model.responses = [{"action": "respond", "message": "Recovered."}]
            status, done = self.utter("Continue", session=session, interaction="CONTINUE")
            self.assertEqual(done["task"]["status"], "completed")

    def test_provider_secret_echo_is_redacted_before_next_http_request(self):
        self.model.responses = [{"action": "respond", "message": "test-provider-secret"}]
        status, first = self.utter()
        self.assertEqual(status, 200)
        self.assertNotIn("test-provider-secret", json.dumps(first))
        self.model.responses = [{"action": "respond", "message": "Next"}]
        self.utter("Continue", interaction="NEXT")
        self.assertNotIn("test-provider-secret", json.dumps(self.model.requests[-1][0]))

    def test_authorization_token_echo_is_redacted_without_bearer_prefix(self):
        self.model.responses = [{"action": "respond", "message": "server-secret"}]
        _, response = self.utter()
        self.assertNotIn("server-secret", json.dumps(response))

    def test_backend_request_id_echo_is_redacted_from_model_history(self):
        self.mcp.call_tool = lambda name, arguments: {"request_id": "Bearer server-secret", "data": []}
        self.model.responses = [tool("medical.list_departments"), {"action": "respond", "message": "Read."}]
        self.utter()
        self.assertNotIn("server-secret", json.dumps(self.model.requests[-1][0]))

    def test_model_cannot_place_provider_credentials_in_proposed_arguments(self):
        self.model.responses = [tool("medical.list_appointment_services"), tool("medical.search_appointment_slots", service_id="SVC-PT", date_from="2026-10-14", date_to="2026-10-14"), tool("medical.create_appointment", service_id="SVC-PT", slot_id="SLOT-PT", administrative_note="test-provider-secret")]
        _, result = self.utter()
        self.assertIsNone(result["confirmation"])
        self.assertEqual(result["recovery"]["reason"], "TOOL_REJECTED")
        self.assertNotIn("test-provider-secret", json.dumps(result))
        self.assertEqual(len(self.mcp.calls), 2)

    def test_multiple_native_tool_calls_are_rejected_before_any_execution(self):
        self.model.responses = [{"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "ONE", "type": "function", "function": {"name": "medical__list_departments", "arguments": "{}"}},
            {"id": "TWO", "type": "function", "function": {"name": "medical__get_my_appointments", "arguments": "{}"}},
        ]}}]}]
        _, failed = self.utter()
        self.assertEqual(failed["recovery"]["reason"], "MODEL_FAILURE")
        self.assertEqual(self.mcp.calls, [])

