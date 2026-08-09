"""English time semantics and presentation/authorization separation."""
from copy import deepcopy
import unittest

from middleware.demo_locale import display_value, response_locale
from middleware.demo_medical_workflow import DemoMedicalWorkflow
from middleware.demo_time import english_clock_time, parse_time_constraint, selection_target


class EnglishDemoTests(unittest.TestCase):
    def test_pm_boundaries_are_not_collapsed_to_three(self):
        for text, expected in (
            ("Only after 3 PM", {"kind": "lower_bound", "time": "15:00", "inclusive": False}),
            ("Only after 3:30 PM", {"kind": "lower_bound", "time": "15:30", "inclusive": False}),
            ("Not before 3 PM", {"kind": "lower_bound", "time": "15:00", "inclusive": True}),
            ("No earlier than 3:30 PM", {"kind": "lower_bound", "time": "15:30", "inclusive": True}),
            ("Change it to exactly 3:30 PM", {"kind": "exact", "time": "15:30"}),
            ("I want a cardiology appointment next Tuesday at 3:30 PM", {"kind": "exact", "time": "15:30"}),
        ):
            with self.subTest(text=text): self.assertEqual(parse_time_constraint(text), expected)

    def test_clock_conversion_and_unsupported_hours_fail_closed(self):
        self.assertEqual(english_clock_time("12 PM"), "12:00")
        self.assertEqual(english_clock_time("12 AM"), "00:00")
        for text in ("Book cardiology at 11 AM", "Change to 6 PM"):
            self.assertTrue(DemoMedicalWorkflow._unsupported_intent(text, "2026-10-20"))
        self.assertFalse(DemoMedicalWorkflow._unsupported_intent("Not before 3 PM", "2026-10-20"))
        self.assertIsNone(english_clock_time("3:90 PM"))

    def test_pm_selection_and_ordinal_preserve_their_meaning(self):
        self.assertEqual(selection_target("The 3:30 PM one, please"), {"kind": "time", "time": "15:30"})
        self.assertEqual(selection_target("The second one", {"presentation_id": "P-1"}),
                         {"kind": "ordinal", "ordinal": 2, "presentation_id": "P-1"})

    def test_locale_is_presentation_metadata_and_persists_without_a_hint(self):
        self.assertEqual(response_locale({}, "Book cardiology next Tuesday"), "en")
        self.assertEqual(response_locale({}, previous="en"), "en")
        self.assertEqual(response_locale({"locale": "zh-Hant"}, previous="en"), "zh-Hant")
        for invalid in (None, [], {}, "unknown"):
            self.assertEqual(response_locale({"locale": invalid}, previous="en"), "en")

    def test_localization_never_mutates_an_approval_event_or_receipt_id(self):
        event = {"type": "confirmation_decision", "decision": "approve", "confirmation_id": "CONF-心臟科"}
        original = {"title": "確認預約", "actions": [{"label": "確認掛號", "event": event}], "receipt_id": "R-心臟科"}
        saved = deepcopy(original)
        translated = display_value(original)
        self.assertEqual(translated["actions"][0]["label"], "Approve booking")
        self.assertEqual(translated["actions"][0]["event"], event)
        self.assertEqual(translated["receipt_id"], "R-心臟科")
        self.assertEqual(original, saved)


if __name__ == "__main__": unittest.main()
