import copy
import json
import unittest
from MCP.registry import build_registry
from middleware.agent import AgentProtocolError, RegistryDrivenAgent
from middleware.llm_transport import ChatCompletionError, OpenAICompatibleChatClient
from middleware.tests.test_agent import RecordingExecutor
from middleware.tests.test_agent_protocol import native_call, native_finalizer
from middleware.tests import test_agent_provider_http as http_fixture


def prose(content='**Read completed.**', reason='stop', role='assistant', **extra):
    return {'choices': [{'finish_reason': reason, 'message': {'role': role, 'content': content, **extra}}]}


class FinalNormalizationTests(unittest.TestCase):
    def decide(self, responses, enabled=True):
        self.requests = []
        def provider(request, timeout):
            self.requests.append(json.loads(request.data))
            return responses.pop(0)
        client = OpenAICompatibleChatClient('http://fixture.test/chat', transport=provider, normalize_final_response=enabled)
        executor = RecordingExecutor()
        self.agent = RegistryDrivenAgent(build_registry(), client, executor)
        return self.agent.decide(self.history)

    def setUp(self):
        self.history = [{'role': 'system', 'content': 'Server policy'}, {'role': 'user', 'content': 'Read'}]

    def test_one_tool_free_repair_preserves_history(self):
        original = copy.deepcopy(self.history)
        decision = self.decide([prose(), prose('{"action":"respond","message":"Read completed."}')])
        self.assertEqual((decision.action, decision.message), ('respond', 'Read completed.'))
        self.assertEqual(self.history, original)
        self.assertEqual(len(self.requests), 2)
        repair = self.requests[1]
        self.assertNotIn('tools', repair)
        self.assertNotIn('tool_choice', repair)
        self.assertEqual(repair['messages'][:-2], original)
        self.assertEqual(repair['messages'][-2]['content'], '**Read completed.**')
        self.assertEqual(repair['messages'][-1]['role'], 'system')

    def test_ineligible_outputs_never_repair(self):
        cases = [prose('{broken'), prose('[broken'), prose(''), prose('x', reason=None), prose('x', reason='length'), prose('x', reason='content_filter'), prose('x', role='user'), prose('x', tool_calls={}), native_call(call_type='invalid')]
        for response in cases:
            with self.subTest(response=response):
                with self.assertRaises((AgentProtocolError, ChatCompletionError)):
                    self.decide([response])
                self.assertEqual(len(self.requests), 1)
        with self.assertRaises(AgentProtocolError):
            self.decide([prose()], enabled=False)
        self.assertEqual(len(self.requests), 1)

    def test_repair_rejects_operations_native_calls_and_repeated_prose(self):
        cases = [prose(), native_call(), native_finalizer('ponte__respond', 'Done'), prose('{"action":"tool_call","tool_name":"medical.create_appointment","arguments":{}}'), prose('{"action":"respond","message":"Done","decision":"approve"}')]
        for response in cases:
            with self.subTest(response=response):
                with self.assertRaises((AgentProtocolError, ChatCompletionError)):
                    self.decide([prose(), response])
                self.assertEqual(len(self.requests), 2)


class FinalNormalizationHttpTests(unittest.TestCase):
    setUp = http_fixture.AgentProviderHttpTests.setUp
    tearDown = http_fixture.AgentProviderHttpTests.tearDown
    post = http_fixture.AgentProviderHttpTests.post
    utter = http_fixture.AgentProviderHttpTests.utter
    def test_read_final_repair_through_canonical_http(self):
        self.app.interaction_core.agent_orchestrator.agent.client.normalize_final_response = True
        from middleware.tests.test_agent_orchestrator import tool
        self.model.responses = [tool('medical.list_departments'), prose(), {'action': 'respond', 'message': 'Read completed.'}]
        status, result = self.utter()
        self.assertEqual(status, 200)
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(result['response']['display_text'], 'Read completed.')
        self.assertEqual(len(self.mcp.calls), 1)
        self.assertIsNone(result['confirmation'])
        self.assertIsNone(result['receipt'])
        self.model.responses = [{'action': 'respond', 'message': 'Next'}]
        self.utter('Continue', interaction='NEXT')
        messages = self.model.requests[-1][0]
        self.assertNotIn('**Read completed.**', json.dumps(messages))
        self.assertIn('Read completed.', json.dumps(messages))

