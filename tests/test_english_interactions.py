"""English preferences through main HTTP, real MCP, and mock services."""
import copy
import unittest

from tests import test_full_stack_integration as fixture


class EnglishInteractionTests(unittest.TestCase):
    setUp = fixture.FullStackIntegrationTests.setUp
    tearDown = fixture.FullStackIntegrationTests.tearDown
    post_middleware = fixture.FullStackIntegrationTests.post_middleware

    def interact(self, event, interaction, locale=None, session="ENGLISH"):
        body = fixture.interaction_body(session, interaction, event)
        if locale: body["audit"] = {"locale":locale}
        return self.post_middleware("/api/interactions",body)

    def test_english_booking_retains_issued_events_and_can_switch_before_confirmation(self):
        first = self.interact(fixture.utterance("I would like to book a medical appointment."),"EN-1","en")
        self.assertIn("medical services",first["response"]["display_text"])
        self.assertEqual(first["response"]["speech_locale"],"en-US")
        self.assertEqual(first["workspace"]["title"],"Choose a medical service")
        action = next(a["event"] for a in first["workspace"]["actions"] if a["label"] == "Physical therapy")
        field = next(f for f in first["workspace"]["fields"] if f["label"] == "Physical therapy")
        self.assertEqual(field["action"]["event"],action)
        slots = self.interact(action,"EN-2")
        self.assertEqual(slots["workspace"]["title"],"Choose an appointment time")
        self.assertIn("Please choose a time",slots["response"]["display_text"])
        pending = self.interact(slots["workspace"]["actions"][0]["event"],"EN-3")
        self.assertEqual(pending["task"]["status"],"awaiting_confirmation")
        approved = next(a["event"] for a in pending["workspace"]["actions"] if a["event"].get("decision") == "approve")
        original = copy.deepcopy(approved)
        done = self.interact(approved,"ZH-CONFIRM","zh-Hant")
        self.assertEqual(approved,original)
        self.assertEqual(done["task"]["status"],"completed")
        self.assertIn("預約已完成",done["response"]["display_text"])
        replay = self.interact(approved,"EN-REPLAY","en")
        self.assertEqual(replay["receipt"],done["receipt"])
        self.assertIn("confirmed",replay["response"]["display_text"])

    def test_english_readonly_queries_and_chinese_mode(self):
        appointments = self.interact(fixture.utterance("I would like to see my medical appointments."),"READ-1","en")
        self.assertEqual(appointments["workspace"]["view"],"appointment_list")
        self.assertIn("appointment records",appointments["response"]["display_text"])
        cash = self.interact(fixture.utterance("I would like to check the cash sharing scheme."),"CASH-1","en",session="CASH")
        self.assertIn("read-only",cash["response"]["display_text"])
        self.assertEqual(cash["workspace"]["title"],"Cash sharing scheme")
        self.assertIn("Plan name",[f["label"] for f in cash["workspace"]["fields"]])
        chinese = self.interact(fixture.utterance("我想查現金分享計劃"),"ZH-CASH","zh-Hant",session="ZH")
        self.assertIn("我已查到",chinese["response"]["display_text"])
