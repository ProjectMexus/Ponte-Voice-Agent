"""Restored domain workflow and main agent coexist behind one canonical core."""
import unittest
import re
from middleware.agent_orchestrator import AgentOrchestrator
from middleware.execution import ContextualExecutionPipeline
from middleware.tests.test_agent_orchestrator import ScriptedModel
from tests import test_english_medical_demo_e2e as english_demo


class IntegratedCardiologyRoutingTests(unittest.TestCase):
    def setUp(self):
        self.demo = english_demo.EnglishMedicalDemoEndToEndTests()
        self.addCleanup(self.demo.doCleanups)
        self.demo.setUp()
        app = self.demo.harness.app
        self.general_model = ScriptedModel([
            {"action": "respond", "message": "Your existing medical appointments remain recorded."}
        ])
        app.interaction_core.agent_orchestrator = AgentOrchestrator(
            app.registry, self.general_model, ContextualExecutionPipeline(app.pipeline),
            app.medical_workflow,
            {"patient_id": app.patient_id, "authorization": app.authorization,
             "mock_user_id": app.mock_user_id, "accept_language": "en"},
        )

    def test_seven_turns_use_domain_runtime_then_general_agent_remains_available(self):
        self.demo.test_seven_english_turns_confirm_receipt_and_replay_once()
        self.assertEqual(len(self.general_model.requests), 0)
        result = self.demo.harness.say("Show me my medical appointments.")
        self.assertEqual(result["response_intent"] if "response_intent" in result else result["workspace"]["view"], "agent_task")
        self.assertEqual(len(self.general_model.requests), 1)
        self.assertEqual(len(self.demo.live.write_dispatches()), 1)

    def test_draft_response_and_operation_replay_are_english_and_never_claim_booking(self):
        result = self.demo.say(english_demo.REQUEST)
        self.assertIn("draft", result["response"]["display_text"].lower())
        self.assertIn("no appointment", result["response"]["display_text"].lower())
        for event in result["workspace"]["activity"]:
            self.assertIsNone(re.search(r"[\u3400-\u9fff]", event.get("title", "") + event.get("detail", "")))
        self.assertEqual(self.demo.live.write_dispatches(), [])

    def test_active_general_proposal_cannot_be_abandoned_by_cardiology_request(self):
        core = self.demo.harness.app.interaction_core
        state = core.sessions.get_or_create("ROUTING-TEST")
        state.task = {"task_id": "GENERAL", "type": "agent", "status": "awaiting_confirmation"}
        from middleware.interaction_contracts import EventEnvelope
        envelope = EventEnvelope.from_json({"routing": {"session_id": "ROUTING-TEST", "interaction_id": "NEW"},
            "event": {"type": "user_utterance", "content": "Book cardiology next Tuesday afternoon"}})
        self.assertFalse(core._uses_demo(state, envelope))
