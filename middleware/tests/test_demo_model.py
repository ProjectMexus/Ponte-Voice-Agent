from copy import deepcopy
import json
import re
import unittest

from MCP.registry import build_registry
from middleware.agent import AgentProtocolError, parse_agent_decision, project_registry_tools
from middleware.demo_medical_workflow import ALLOWLIST, DemoMedicalWorkflow
from middleware.demo_model import MODEL_TOOL_ALIASES, RegistryToolNameClient, ScriptedCardiologyClient
from middleware.tests.test_demo_medical_workflow import MemoryPipeline, NOW, REQUEST, envelope
from mock_backends.core.clock import FixedClock


def native_call(name, call_id="provider-call-1", arguments=None):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{
        "id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments or {})},
    }]}}]}


class FakeTransportClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def complete(self, messages, **options):
        self.requests.append((deepcopy(messages), deepcopy(options)))
        for tool in options.get("tools", []):
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", tool["function"]["name"]):
                raise AssertionError("provider received an invalid function name")
        return self.responses.pop(0)


class RegistryToolNameClientTests(unittest.TestCase):
    def test_scripted_controls_classify_paraphrases_without_turn_numbers(self):
        client = ScriptedCardiologyClient()
        cases = [
            ("Can you check my appointments?", {"action": "query_appointments"}),
            ("Would that overlap?", {"action": "answer_question"}),
            ("Let's return to the booking", {"action": "resume_booking"}),
            ("Select that slot", {"action": "select_slot"}),
            ("下午三點後先得", {"action": "update_constraints", "after_three": True}),
            ("改為兩點", {"action": "update_constraints", "after_three": False}),
        ]
        for content, expected in cases:
            with self.subTest(content=content):
                response = client.complete([{"role": "user", "content": content}], demo_control=True)
                self.assertEqual(json.loads(response["choices"][0]["message"]["content"]), expected)

    def tools(self):
        return [tool for tool in project_registry_tools(build_registry()) if tool["function"]["name"] in ALLOWLIST]

    def test_native_alias_roundtrip_preserves_call_id_arguments_and_inputs(self):
        provider_response = native_call("medical_list_departments", arguments={"keyword": "Cardiology", "active_only": True})
        original_response = deepcopy(provider_response)
        transport = FakeTransportClient(provider_response)
        client = RegistryToolNameClient(transport)
        tools = self.tools()
        original_tools = deepcopy(tools)
        response = client.complete([{"role": "user", "content": REQUEST}], tools=tools, tool_choice={"type": "function", "function": {"name": "medical.list_departments"}})
        sent = transport.requests[0][1]
        self.assertEqual({tool["function"]["name"] for tool in sent["tools"]}, set(MODEL_TOOL_ALIASES.values()))
        self.assertEqual(sent["tool_choice"]["function"]["name"], "medical_list_departments")
        call = response["choices"][0]["message"]["tool_calls"][0]
        self.assertEqual(call["id"], "provider-call-1")
        self.assertEqual(call["function"]["name"], "medical.list_departments")
        self.assertEqual(call["function"]["arguments"], original_response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
        self.assertEqual(tools, original_tools)
        self.assertEqual(provider_response, original_response)
        self.assertEqual(parse_agent_decision(response).tool_name, "medical.list_departments")

    def test_history_translates_names_without_changing_pairing_or_logical_transcript(self):
        history = [
            {"role": "system", "content": "test"},
            native_call("medical.list_departments", "original-call")["choices"][0]["message"],
            {"role": "tool", "tool_call_id": "original-call", "content": '{"tool_name":"medical.list_departments","ok":true}'},
            {"role": "user", "content": "continue"},
        ]
        original = deepcopy(history)
        transport = FakeTransportClient(native_call("medical_search_registration_slots", "next-call"))
        response = RegistryToolNameClient(transport).complete(history, tools=self.tools())
        sent = transport.requests[0][0]
        self.assertEqual(sent[1]["tool_calls"][0]["function"]["name"], "medical_list_departments")
        self.assertEqual(sent[1]["tool_calls"][0]["id"], sent[2]["tool_call_id"])
        self.assertEqual(sent[2], original[2])
        self.assertEqual(history, original)
        self.assertEqual(response["choices"][0]["message"]["tool_calls"][0]["id"], "next-call")

    def test_multiple_calls_remain_multiple_and_are_rejected_by_existing_parser(self):
        response = native_call("medical_list_departments")
        response["choices"][0]["message"]["tool_calls"].extend(native_call("medical_search_registration_slots", "call-2")["choices"][0]["message"]["tool_calls"])
        translated = RegistryToolNameClient(FakeTransportClient(response)).complete([], tools=self.tools())
        self.assertEqual(len(translated["choices"][0]["message"]["tool_calls"]), 2)
        with self.assertRaises(AgentProtocolError):
            parse_agent_decision(translated)

    def test_unsupported_alias_never_becomes_an_allowed_registry_tool(self):
        for name in ("medical_delete_registration", "one_account_get_cash_sharing_plan", "medical__create_registration"):
            with self.subTest(name=name):
                provider = FakeTransportClient(native_call(name))
                client = RegistryToolNameClient(provider)
                decision = parse_agent_decision(client.complete([], tools=self.tools()))
                self.assertEqual(decision.tool_name, name)
                self.assertNotIn(decision.tool_name, ALLOWLIST)
                pipeline = MemoryPipeline()
                provider.responses.append(native_call(name))
                workflow = DemoMedicalWorkflow(pipeline, "PAT-UNIT", "Bearer test", registry=build_registry(), client=client, clock=FixedClock(NOW))
                _, result, _ = workflow.start(envelope({"type": "user_utterance", "content": REQUEST}))
                self.assertEqual(result.recovery["reason"], "agent_protocol_error")
                self.assertEqual(pipeline.calls, [])

    def test_strict_json_action_maps_only_exact_known_tool_names(self):
        for direct in (True, False):
            for name, expected in (("medical_list_departments", "medical.list_departments"), ("medical_delete_registration", "medical_delete_registration")):
                with self.subTest(direct=direct, name=name):
                    action = {"action": "tool_call", "tool_name": name, "arguments": {"keyword": "Cardiology"}}
                    response = action if direct else {"choices": [{"message": {"content": json.dumps(action)}}]}
                    translated = RegistryToolNameClient(FakeTransportClient(response)).complete([], tools=self.tools())
                    self.assertEqual(parse_agent_decision(translated).tool_name, expected)

    def test_workflow_keeps_logical_names_and_original_provider_ids_through_alias_transport(self):
        pipeline = MemoryPipeline()
        transport = FakeTransportClient(
            native_call("medical_list_departments", "call-departments", {"keyword": "Cardiology", "active_only": True}),
            native_call("medical_search_registration_slots", "call-search", {"department_id": "DEPT-CARDIO", "date": "2026-10-20", "session": "afternoon"}),
            native_call("medical_create_registration", "call-proposal", {"department_id": "DEPT-CARDIO", "slot_id": pipeline.slots[0]["id"], "consent": True}),
        )
        workflow = DemoMedicalWorkflow(pipeline, "PAT-UNIT", "Bearer test", registry=build_registry(), client=RegistryToolNameClient(transport), clock=FixedClock(NOW))
        task, result, _ = workflow.start(envelope({"type": "user_utterance", "content": REQUEST}))
        self.assertEqual(result.task["status"], "awaiting_input")
        transcript = workflow.transcript(task["task_id"])
        calls = [message["tool_calls"][0] for message in transcript if message.get("tool_calls")]
        self.assertEqual([call["id"] for call in calls], ["call-departments", "call-search", "call-proposal"])
        self.assertEqual({call["function"]["name"] for call in calls}, ALLOWLIST - {"medical.get_my_appointments"})
        self.assertEqual([call.name for call in pipeline.calls], ["medical.list_departments", "medical.search_registration_slots"])
        sent_calls = [call for message in transport.requests[-1][0] for call in message.get("tool_calls", [])]
        self.assertEqual(next(call for call in sent_calls if call["id"] == "call-departments")["function"]["name"], "medical_list_departments")


if __name__ == "__main__":
    unittest.main()
