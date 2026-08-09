import json
import math
import unittest
from unittest.mock import patch
from middleware.llm_transport import OpenAICompatibleChatClient
from middleware.llm_configuration import agent_chat_client_from_environment

class AgentLlmConfigurationTests(unittest.TestCase):
    def test_qwen_endpoint_disables_thinking_and_sets_bounded_timeout(self):
        client = agent_chat_client_from_environment({'PONTE_LLM_API_URL':'https://maas.qwencloudapi.com/compatible-mode/v1/chat/completions','PONTE_LLM_API_KEY':'fixture','PONTE_LLM_MODEL':'qwen3.7-plus'})
        captured=[]
        client._transport=lambda request,timeout: captured.append((json.loads(request.data),timeout)) or {'choices':[{'message':{'content':'{}'}}]}
        client.complete([{'role':'user','content':'json test'}])
        self.assertIs(captured[0][0]['enable_thinking'],False)
        self.assertEqual(captured[0][1],30.0)
        self.assertEqual(captured[0][0]['model'],'qwen3.7-plus')
        self.assertTrue(client.normalize_final_response)

    def test_generic_endpoint_omits_provider_specific_thinking_option(self):
        client=agent_chat_client_from_environment({'PONTE_LLM_API_URL':'https://example.invalid/chat/completions','PONTE_LLM_MODEL':'fixture','PONTE_LLM_TIMEOUT_SECONDS':'12.5'})
        captured=[]
        client._transport=lambda request,timeout: captured.append((json.loads(request.data),timeout)) or {}
        client.complete([])
        self.assertNotIn('enable_thinking',captured[0][0])
        self.assertEqual(captured[0][1],12.5)
        self.assertFalse(client.normalize_final_response)

    def test_explicit_nonthinking_mode_is_forwarded(self):
        client=agent_chat_client_from_environment({'PONTE_LLM_API_URL':'https://example.invalid/chat/completions','PONTE_LLM_ENABLE_THINKING':'false'})
        self.assertIs(client.enable_thinking,False)

    def test_unsupported_or_invalid_thinking_configuration_fails_closed(self):
        for value in ('true','maybe'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                agent_chat_client_from_environment({'PONTE_LLM_API_URL':'https://example.invalid/chat/completions','PONTE_LLM_ENABLE_THINKING':value})

    def test_timeout_rejects_nonfinite_and_nonpositive_values(self):
        for value in ('0','-1','nan','inf','not-a-number'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                agent_chat_client_from_environment({'PONTE_LLM_API_URL':'https://example.invalid/chat/completions','PONTE_LLM_TIMEOUT_SECONDS':value})

    def test_direct_transport_rejects_invalid_timeout(self):
        for value in (0,-1,math.nan,math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                OpenAICompatibleChatClient('https://example.invalid',timeout=value)
