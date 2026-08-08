"""Inspect serialized HTTP requests, beyond the fake completion interface."""

from copy import deepcopy
import json
import unittest

from MCP.registry import build_registry
from middleware.demo_medical_workflow import DemoMedicalWorkflow
from middleware.demo_model import MODEL_TOOL_ALIASES, RegistryToolNameClient
from middleware.llm_transport import OpenAICompatibleChatClient
from middleware.tests.test_demo_medical_workflow import MemoryPipeline, NOW, envelope
from middleware.tests.test_demo_model import native_call
from mock_backends.core.clock import FixedClock


class OpenAIPayloadTests(unittest.TestCase):
    def setUp(self):
        self.payloads = []
        self.responses = []

        def transport(request, timeout):
            self.assertEqual(request.get_method(), "POST")
            payload = json.loads(request.data)
            self.assertEqual(payload["model"], "gpt-4.1-mini")
            functions = [tool["function"] for tool in payload.get("tools", [])]
            for message in payload["messages"]:
                functions.extend(call["function"] for call in message.get("tool_calls", []))
            choice = payload.get("tool_choice")
            if isinstance(choice, dict):
                functions.append(choice["function"])
            for function in functions:
                self.assertRegex(function["name"], r"^[a-zA-Z0-9_-]{1,64}$")
            self.payloads.append(payload)
            return self.responses.pop(0)

        self.client = RegistryToolNameClient(OpenAICompatibleChatClient(
            "https://api.openai.com/v1/chat/completions", model="gpt-4.1-mini", transport=transport,
        ))
        self.pipeline = MemoryPipeline()
        self.workflow = DemoMedicalWorkflow(
            self.pipeline, "PAT-UNIT", "Bearer test", registry=build_registry(),
            client=self.client, clock=FixedClock(NOW),
        )

    def test_all_aliases_and_named_choice_reach_http_and_roundtrip(self):
        for registry_name, alias in MODEL_TOOL_ALIASES.items():
            with self.subTest(name=registry_name):
                self.responses.append(native_call(alias, "original-id", {"consent": True}))
                messages = [{"role": "system", "content": f"Use {registry_name} or {registry_name.split('.')[1]}."},
                            {"role": "user", "content": registry_name}]
                original = deepcopy(messages)
                result = self.client.complete(messages, tools=self.workflow.tools,
                    tool_choice={"type": "function", "function": {"name": registry_name}})
                payload = self.payloads[-1]
                self.assertEqual(payload["tool_choice"]["function"]["name"], alias)
                self.assertEqual(payload["messages"][0]["content"], f"Use {alias} or {alias}.")
                self.assertEqual(payload["messages"][1], messages[1])
                call = result["choices"][0]["message"]["tool_calls"][0]
                self.assertEqual(call["function"]["name"], registry_name)
                self.assertEqual(call["id"], "original-id")
                self.assertEqual(call["function"]["arguments"], '{"consent": true}')
                self.assertEqual(messages, original)

    def test_superseded_p1_keeps_provider_id_and_pairs_before_new_intent(self):
        self.responses.extend([
            native_call("medical_list_departments", "dept", {"keyword": "Cardiology", "active_only": True}),
            native_call("medical_search_registration_slots", "search", {"department_id": "DEPT-CARDIO", "date": "2026-10-20", "session": "afternoon"}),
            native_call("medical_create_registration", "P1-provider-id", {"department_id": "DEPT-CARDIO", "slot_id": self.pipeline.slots[0]["id"], "consent": True}),
            {"choices": [{"message": {"content": json.dumps({"action": "update_constraints", "time_constraint": {"kind":"lower_bound","time":"15:00","inclusive":False}})}}]},
            native_call("medical_search_registration_slots", "search-revised", {"department_id": "DEPT-CARDIO", "date": "2026-10-20", "session": "afternoon"}),
            native_call("medical_create_registration", "P2-provider-id", {"department_id": "DEPT-CARDIO", "slot_id": self.pipeline.slots[1]["id"], "consent": True}),
        ])
        task, p1, _ = self.workflow.start(envelope({"type": "user_utterance", "content": "心臟科下週二下午"}))
        self.assertEqual(p1.task["status"], "awaiting_input")
        task, p2, _ = self.workflow.handle(task, envelope({"type": "user_utterance", "content": "改為下午3點後"}))
        self.assertEqual(p2.task["status"], "awaiting_input")
        sent = self.payloads[-1]["messages"]
        self.assertIn("medical_create_registration call", sent[0]["content"])
        pending = {}
        for index, message in enumerate(sent):
            for call in message.get("tool_calls", []):
                pending[call["id"]] = call
            if message["role"] == "tool":
                call = pending.pop(message["tool_call_id"])
                if message["tool_call_id"] == "P1-provider-id":
                    self.assertEqual(call["function"]["name"], "medical_create_registration")
                    self.assertIn("DRAFT_ONLY", message["content"])
                    self.assertFalse(json.loads(message["content"])["executed"])
                    self.assertEqual(sent[index + 1]["content"], "改為下午3點後")
        self.assertEqual(pending, {})
        transcript = self.workflow.transcript(task["task_id"])
        self.assertEqual(transcript[-2]["tool_calls"][0]["id"], "P2-provider-id")
        self.assertEqual(transcript[-2]["tool_calls"][0]["function"]["name"], "medical.create_registration")
        self.assertEqual(transcript[-1]["tool_call_id"], "P2-provider-id")
        self.assertNotIn("demo_control", self.payloads[-1])
        self.assertNotIn("medical.create_registration", [call.name for call in self.pipeline.calls])

    def test_multiple_calls_from_http_execute_neither(self):
        response = native_call("medical_list_departments", "first", {"keyword": "Cardiology", "active_only": True})
        response["choices"][0]["message"]["tool_calls"].extend(
            native_call("medical_search_registration_slots", "second")["choices"][0]["message"]["tool_calls"])
        self.responses.append(response)
        _, result, _ = self.workflow.start(envelope({"type": "user_utterance", "content": "心臟科下週二下午"}))
        self.assertEqual(result.recovery["reason"], "agent_protocol_error")
        self.assertEqual(self.pipeline.calls, [])


if __name__ == "__main__":
    unittest.main()
