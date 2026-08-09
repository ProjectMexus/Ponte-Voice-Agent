"""Provider decision edge cases and sequential native function requests."""
import json
import unittest

from MCP.registry import build_registry
from middleware.agent import AgentProtocolError, RegistryDrivenAgent, parse_agent_decision
from middleware.llm_transport import ChatCompletionError, OpenAICompatibleChatClient
from middleware.tests.test_agent import RecordingExecutor


def native_call(*, call_type="function", finish_reason="tool_calls"):
    return {"choices": [{"finish_reason": finish_reason, "message": {
        "role": "assistant", "content": None, "tool_calls": [{
            "id": "PROVIDER-1", "type": call_type,
            "function": {"name": "medical.list_departments", "arguments": "{}"},
        }],
    }}]}


def native_finalizer(name, message, **extra):
    response = native_call()
    function = response["choices"][0]["message"]["tool_calls"][0]["function"]
    function["name"] = name
    function["arguments"] = json.dumps({"message": message, **extra})
    return response


class AgentProtocolTests(unittest.TestCase):
    def test_native_finalizers_are_closed_text_decisions(self):
        for name, action in (("ponte__respond", "respond"), ("ponte__clarify", "clarify")):
            with self.subTest(name=name):
                decision = parse_agent_decision(native_finalizer(name, "Next step."))
                self.assertEqual((decision.action, decision.message), (action, "Next step."))
                self.assertIsNone(decision.tool_name)
                self.assertIsNone(decision.arguments)

    def test_native_finalizers_cannot_carry_approval_or_operation_arguments(self):
        for extra in ({"decision": "approve"}, {"action": "approve"}, {"tool_name": "medical.create_appointment"}, {"arguments": {}}):
            with self.subTest(extra=extra):
                with self.assertRaises(AgentProtocolError):
                    parse_agent_decision(native_finalizer("ponte__respond", "Confirm.", **extra))
        for message in (None, "", "   ", 7):
            with self.subTest(message=message):
                with self.assertRaises(AgentProtocolError):
                    parse_agent_decision(native_finalizer("ponte__clarify", message))

    def test_finalizer_request_catalog_leaves_registry_projection_unchanged(self):
        def provider(request, timeout):
            payload = json.loads(request.data)
            functions = {tool["function"]["name"]: tool["function"] for tool in payload["tools"]}
            for name in ("ponte__respond", "ponte__clarify"):
                self.assertEqual(functions[name]["parameters"], {
                    "type": "object", "properties": {"message": {"type": "string"}},
                    "required": ["message"], "additionalProperties": False,
                })
            return native_finalizer("ponte__respond", "Done.")
        client = OpenAICompatibleChatClient("http://provider.test/chat", transport=provider)
        agent = RegistryDrivenAgent(build_registry(), client, RecordingExecutor())
        decision = agent.decide([{"role": "user", "content": "Finish the answer"}])
        self.assertEqual((decision.action, decision.message), ("respond", "Done."))
        self.assertEqual(len(agent.tools), 21)
        self.assertFalse(any(t["function"]["name"].startswith("ponte__") for t in agent.tools))

    def test_standalone_finalizer_completes_without_external_execution(self):
        def provider(request, timeout):
            functions = {t["function"]["name"] for t in json.loads(request.data)["tools"]}
            if "ponte__respond" not in functions:
                return {"choices": [{"message": {"content": "**Done.**"}}]}
            return native_finalizer("ponte__respond", "Done.")
        client = OpenAICompatibleChatClient("http://provider.test/chat", transport=provider)
        executor = RecordingExecutor()
        outcome = RegistryDrivenAgent(build_registry(), client, executor).run("Finish the answer")
        self.assertEqual((outcome.kind, outcome.message), ("respond", "Done."))
        self.assertEqual(executor.calls, [])

    def test_provided_service_catalog_cannot_shadow_reserved_finalizer(self):
        def provider(request, timeout):
            raise AssertionError("colliding tool catalog must fail before provider I/O")
        client = OpenAICompatibleChatClient("http://provider.test/chat", transport=provider)
        agent = RegistryDrivenAgent(build_registry(), client, RecordingExecutor())
        for name in ("ponte__respond", "ponte__clarify"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    agent.decide([{"role": "user", "content": "Finish"}], tools=[{
                        "type": "function", "function": {"name": name, "parameters": {"type": "object"}},
                    }])

    def test_plain_markdown_remains_outside_closed_decision_protocol(self):
        with self.assertRaises(AgentProtocolError):
            parse_agent_decision({"choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "content": "**Done.**",
            }}]})

    def test_empty_native_call_list_allows_final_json_response(self):
        response = {"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "tool_calls": [],
            "content": '{"action":"respond","message":"Done."}',
        }}]}
        decision = parse_agent_decision(response)
        self.assertEqual((decision.action, decision.message), ("respond", "Done."))

    def test_explicit_non_function_native_call_is_rejected(self):
        for call_type in ("not_function", None, 7):
            with self.subTest(call_type=call_type):
                with self.assertRaises(AgentProtocolError):
                    parse_agent_decision(native_call(call_type=call_type))

    def test_truncated_or_filtered_native_call_never_dispatches(self):
        for reason in ("length", "content_filter"):
            with self.subTest(reason=reason):
                response = native_call(finish_reason=reason)
                client = OpenAICompatibleChatClient("http://provider.test/chat", transport=lambda request, timeout: response)
                executor = RecordingExecutor()
                result = RegistryDrivenAgent(build_registry(), client, executor).run("Read departments")
                self.assertEqual(result.kind, "clarify")
                self.assertEqual(executor.calls, [])

    def test_truncated_json_response_is_not_completed(self):
        response = {"choices": [{"finish_reason": "length", "message": {
            "role": "assistant", "content": '{"action":"respond","message":"Partial."}',
        }}]}
        with self.assertRaises(ChatCompletionError):
            parse_agent_decision(response)

    def test_absent_provider_metadata_remains_compatible(self):
        response = native_call()
        response["choices"][0].pop("finish_reason")
        response["choices"][0]["message"]["tool_calls"][0].pop("type")
        self.assertEqual(parse_agent_decision(response).action, "tool_call")

    def test_multiple_calls_remain_rejected_even_if_provider_ignores_option(self):
        response = native_call()
        response["choices"][0]["message"]["tool_calls"].append({
            "id": "PROVIDER-2", "type": "function",
            "function": {"name": "medical.get_my_appointments", "arguments": "{}"},
        })
        with self.assertRaises(AgentProtocolError):
            parse_agent_decision(response)

    @staticmethod
    def sequential_provider(request, timeout):
        payload = json.loads(request.data)
        tool_results = sum(message["role"] == "tool" for message in payload["messages"])
        if tool_results == 2:
            return {"choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "tool_calls": [],
                "content": '{"action":"respond","message":"Read completed."}',
            }}]}
        response = native_call()
        if tool_results == 1:
            response["choices"][0]["message"]["tool_calls"][0]["function"]["name"] = "medical.get_my_appointments"
        # A provider may choose two independent reads unless the caller disables
        # parallel calls. Exercise the serialized HTTP request rather than a spy.
        if payload.get("parallel_tool_calls") is not False:
            response["choices"][0]["message"]["tool_calls"].append({
                "id": "PROVIDER-2", "type": "function",
                "function": {"name": "medical.get_my_appointments", "arguments": "{}"},
            })
        return response

    def test_resumable_decision_requests_one_native_call(self):
        client = OpenAICompatibleChatClient("http://provider.test/chat", transport=self.sequential_provider)
        agent = RegistryDrivenAgent(build_registry(), client, RecordingExecutor())
        result = agent.decide([{"role": "user", "content": "Read departments and appointments"}])
        self.assertEqual(result.tool_name, "medical.list_departments")

    def test_standalone_loop_serializes_reads_and_completes(self):
        client = OpenAICompatibleChatClient("http://provider.test/chat", transport=self.sequential_provider)
        executor = RecordingExecutor()
        result = RegistryDrivenAgent(build_registry(), client, executor).run("Read departments and appointments")
        self.assertEqual((result.kind, result.message), ("respond", "Read completed."))
        self.assertEqual([call.name for call, context in executor.calls], [
            "medical.list_departments", "medical.get_my_appointments",
        ])


if __name__ == "__main__":
    unittest.main()
