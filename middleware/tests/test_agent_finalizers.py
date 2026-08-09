"""Native text finalizers through actual provider and canonical HTTP transports."""
import json
import unittest

from middleware.tests.test_agent_orchestrator import tool
from middleware.tests.test_agent_protocol import native_finalizer
from middleware.tests import test_agent_provider_http as http_fixture


class AgentFinalizerHttpTests(unittest.TestCase):
    setUp = http_fixture.AgentProviderHttpTests.setUp
    tearDown = http_fixture.AgentProviderHttpTests.tearDown
    post = http_fixture.AgentProviderHttpTests.post
    utter = http_fixture.AgentProviderHttpTests.utter

    def test_clarify_and_respond_finalizers_do_not_dispatch_or_leave_orphan_history(self):
        self.model.responses = [
            native_finalizer("ponte__clarify", "Which department?"),
            tool("medical.list_departments"),
            native_finalizer("ponte__respond", "The departments were read."),
            native_finalizer("ponte__respond", "You are welcome."),
        ]
        status, clarified = self.utter("Help me find a department", interaction="START")
        self.assertEqual(status, 200)
        self.assertEqual(clarified["task"]["status"], "awaiting_user_input")
        self.assertEqual(clarified["response"]["display_text"], "Which department?")
        self.assertEqual(self.mcp.calls, [])
        task_id = clarified["task"]["task_id"]

        status, completed = self.utter("List all departments", interaction="CONTINUE")
        self.assertEqual(status, 200)
        self.assertEqual(completed["task"]["task_id"], task_id)
        self.assertEqual(completed["task"]["status"], "completed")
        self.assertEqual(completed["response"]["display_text"], "The departments were read.")
        self.assertEqual([name for name, arguments in self.mcp.calls], ["medical.list_departments"])
        self.assertIsNone(completed["confirmation"])
        self.assertIsNone(completed["receipt"])

        self.utter("Thanks", interaction="THANKS")
        messages = self.model.requests[-1][0]
        self.assertEqual([m["role"] for m in messages], [
            "system", "user", "assistant", "user", "assistant", "tool", "assistant", "user",
        ])
        self.assertEqual(messages[2]["content"], "Which department?")
        self.assertEqual(messages[6]["content"], "The departments were read.")
        history_calls = [call for message in messages for call in message.get("tool_calls", [])]
        self.assertEqual([call["function"]["name"] for call in history_calls], ["medical__list_departments"])
        self.assertEqual(len(self.mcp.calls), 1)
        self.assertNotIn("server-secret", json.dumps(messages))

    def test_finalizer_with_approval_fields_pauses_without_external_execution(self):
        self.model.responses = [native_finalizer("ponte__respond", "Confirm.", decision="approve")]
        status, result = self.utter("Book an appointment")
        self.assertEqual(status, 200)
        self.assertEqual(result["recovery"]["reason"], "MODEL_FAILURE")
        self.assertEqual(self.mcp.calls, [])
        self.assertIsNone(result["confirmation"])
        self.assertIsNone(result["receipt"])


if __name__ == "__main__":
    unittest.main()
