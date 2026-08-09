"""English rehearsal through the production scripted client and real HTTP/MCP.

These tests use the opt-in live dataset. They neither substitute queued model
decisions nor change the frozen eight-case multi-turn evaluation.
"""

from copy import deepcopy
import re
import unittest

from middleware.demo_model import ScriptedCardiologyClient
from mock_backends.core.persistence import JsonLinesTextRepository
import tests.test_live_medical_demo_e2e as live


REQUEST = "Book a cardiology appointment next Tuesday afternoon"
AFTER_THREE = "Only after 3 PM"
SLOT_1600 = "SLOT-LIVE-V2-REG-20261020-CARDIO-1600"
CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def strings(value):
    """Walk presentation values without inspecting authoritative task facts."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from strings(item)


class EnglishMedicalDemoEndToEndTests(unittest.TestCase):
    def setUp(self):
        # Reuse v2 fixture/server composition without inheriting its test cases.
        self.live = live.LiveMedicalDemoEndToEndTests()
        self.addCleanup(self.live.doCleanups)
        self.live.setUp()
        self.harness = self.live.harness
        self.harness.app.demo_workflow.client = ScriptedCardiologyClient()

    def assert_english_delivery(self, result):
        response = result["response"]
        for key in ("display_text", "speech_text"):
            self.assertTrue(response[key], result)
            self.assertRegex(response[key], r"[A-Za-z]")
            self.assertIsNone(CJK.search(response[key]), response[key])
        workspace = result["workspace"]
        self.assertTrue(workspace["title"])
        visible = [workspace["title"], workspace["fields"], workspace["actions"],
                   workspace.get("artifact"), result.get("receipt")]
        for text in strings(visible):
            self.assertIsNone(CJK.search(text), text)

    def say(self, text, **kwargs):
        result = self.harness.say(text, **kwargs)
        self.assert_english_delivery(result)
        return result

    def assert_no_execution(self):
        self.assertEqual(self.live.write_dispatches(), [])
        self.assertEqual(self.harness.booking_requests(), [])
        self.assertEqual(self.harness.appointments(), self.live.initial_history)

    def test_seven_english_turns_confirm_receipt_and_replay_once(self):
        # No audit.locale on these requests: the initial English input must
        # establish the presentation language, including the approval response.
        p1 = self.say(REQUEST)
        self.assertEqual(p1["task"]["facts"]["selected_slot"]["id"], live.SLOT_1400)
        self.assertIsNone(p1["task"]["pending_confirmation"])
        p2 = self.say(AFTER_THREE)
        self.assertEqual(p2["task"]["task_id"], p1["task"]["task_id"])
        self.assertEqual(p2["task"]["facts"]["time_constraint"], {
            "kind": "lower_bound", "time": "15:00", "inclusive": False,
        })
        self.assertGreater(p2["task"]["facts"]["intent_revision"],
                           p1["task"]["facts"]["intent_revision"])
        self.assertNotEqual(p2["task"]["facts"]["candidate_id"],
                            p1["task"]["facts"]["candidate_id"])
        self.assertEqual(p2["task"]["facts"]["selected_slot"]["id"], live.SLOT_1530)

        queried = self.say("Wait, do I have any other appointments?")
        snapshot = queried["task"]["facts"]["appointments_snapshot"]
        self.assertEqual(snapshot["source"], "medical.get_my_appointments")
        self.assertEqual({record["id"] for record in snapshot["records"]},
                         {record["id"] for record in self.live.initial_history})
        self.assertEqual(len(snapshot["records"]), 3)
        answered = self.say("Will that clash with my existing appointments?")
        self.assertEqual(answered["task"]["facts"]["appointments_snapshot"], snapshot)
        self.assertEqual(answered["task"]["facts"]["conflict_result"]["status"], "clear")
        searches_before = self.live.search_count()
        resumed = self.say("Go back to the appointment we were booking")
        self.assertGreater(self.live.search_count(), searches_before)
        self.assertEqual(resumed["task"]["task_id"], p2["task"]["task_id"])
        self.assertEqual(resumed["task"]["facts"]["selected_slot"]["id"], live.SLOT_1530)
        self.assertIsNone(resumed["task"]["pending_confirmation"])

        selected = self.say("The 3:30 PM one, please")
        self.assertEqual(selected["task"]["status"], "awaiting_confirmation")
        self.assertEqual(selected["task"]["pending_confirmation"]["appointment"]["time"], "15:30")
        self.assert_no_execution()
        approval = deepcopy(self.harness.approval(selected))
        self.assertEqual(set(approval), {
            "type", "task_id", "confirmation_id", "candidate_id", "decision", "action_id",
        })
        self.assertEqual(approval["type"], "confirmation_decision")
        self.assertEqual(approval["decision"], "approve")
        self.assertEqual(approval["task_id"], p1["task"]["task_id"])
        state = self.harness.app.demo_workflow._states[approval["task_id"]]
        proposal = state.proposals[approval["confirmation_id"]]
        self.assertEqual(dict(proposal.actions)["approve"], approval["action_id"])
        self.assertEqual(proposal.revision, selected["task"]["facts"]["intent_revision"])
        approve_label = next(action["label"] for action in selected["workspace"]["actions"]
                             if action["event"] == approval)
        self.assertRegex(approve_label.casefold(), r"approve|confirm")

        completed = self.harness.interact(approval)
        self.assert_english_delivery(completed)
        self.assertEqual(completed["task"]["status"], "completed")
        receipt = completed["receipt"]
        self.assertRegex(receipt["receipt_id"], r"^MED-REG-\d+$")
        self.assertEqual(receipt["appointment"]["slot_id"], live.SLOT_1530)
        self.assertEqual(receipt["appointment"]["start"], "2026-10-20T15:30:00+08:00")
        self.assertEqual(len(self.live.write_dispatches()), 1)
        self.assertEqual(len(self.harness.booking_requests()), 1)
        records = self.harness.appointments()
        self.assertEqual(len(records), 4)
        booking = next(record for record in records if record["id"] == receipt["appointment"]["appointment_id"])
        self.assertEqual(booking["status"], "booked")
        backend_task = JsonLinesTextRepository(
            self.harness.data_dir / "medical" / "tasks.txt",
        ).get(booking["task_id"])
        self.assertEqual(backend_task["status"], "completed")
        self.assertEqual(backend_task["appointment_id"], booking["id"])
        backend_receipt = next(response.body["receipt"] for request, response in self.harness.router.responses
                               if request.method == "POST" and request.path.endswith("/registrations")
                               and response.status == 201)
        self.assertEqual(backend_receipt["reference"], receipt["receipt_id"])

        repeated = self.harness.interact(approval)
        self.assert_english_delivery(repeated)
        self.assertEqual(repeated["receipt"], receipt)
        self.assertEqual(len(self.live.write_dispatches()), 1)
        self.assertEqual(self.harness.appointments(), records)
        self.harness.assert_pairing(self.harness.transcript(completed))
        self.assertEqual(self.harness.model.requests, [], "The queued oracle must not drive English decisions")

    def test_english_ambiguous_agreement_cannot_execute_or_keep_stale_card(self):
        self.say(REQUEST, audit={"source": "text", "locale": "en"})
        self.say(AFTER_THREE)
        ambiguous = self.say("OK, that should be fine")
        self.live.assert_draft(ambiguous)
        self.assert_no_execution()
        card = self.say("The 3:30 PM one, please")
        self.assertEqual(card["task"]["status"], "awaiting_confirmation")
        old = deepcopy(self.harness.approval(card))
        withdrawn = self.say("OK, that should be fine")
        self.live.assert_draft(withdrawn)
        rejected = self.harness.interact(old, allow_rejection=True)
        self.assertIsNone(rejected.get("receipt"))
        self.assert_no_execution()

    def test_english_pm_exact_and_exclusive_boundaries_select_different_slots(self):
        self.say(REQUEST)
        exact = self.say("Change it to exactly 3:30 PM")
        self.assertEqual(exact["task"]["facts"]["time_constraint"], {
            "kind": "exact", "time": "15:30",
        })
        self.assertEqual(exact["task"]["facts"]["selected_slot"]["id"], live.SLOT_1530)
        after = self.say("Only after 3:30 PM")
        self.assertEqual(after["task"]["facts"]["time_constraint"], {
            "kind": "lower_bound", "time": "15:30", "inclusive": False,
        })
        self.assertEqual(after["task"]["facts"]["selected_slot"]["id"], SLOT_1600)
        self.assertGreater(after["task"]["facts"]["intent_revision"],
                           exact["task"]["facts"]["intent_revision"])
        self.assert_no_execution()

    def test_english_second_option_resolves_presentation_and_obeys_overlap(self):
        draft = self.say(REQUEST)
        presentation = draft["task"]["facts"]["options_presentation"]
        self.assertEqual(presentation["visible_times"], ["14:00", "15:00", "15:30", "16:00"])
        self.assertEqual(presentation["ordered_slot_ids"][1], live.SLOT_1500)
        selected = self.say("The second one, please")
        self.assertEqual(selected["task"]["facts"]["selected_slot"]["id"], live.SLOT_1500)
        self.assertEqual(selected["task"]["facts"]["conflict_result"]["status"], "overlap")
        self.live.assert_draft(selected, live.SLOT_1500)
        self.assert_no_execution()


if __name__ == "__main__":
    unittest.main()
