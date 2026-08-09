"""Opt-in live data acceptance through real HTTP, MCP and isolated backend files.

Only model decisions are queued. These cases are separate from the frozen
eight-case multi-turn evaluation and do not contribute to its reported scores.
"""

from copy import deepcopy
import unittest
from unittest.mock import patch

import tests.test_demo_agent_e2e as h
from middleware.demo_model import ScriptedCardiologyClient
from mock_backends.core.persistence import JsonLinesTextRepository


SLOT_1400 = "SLOT-LIVE-V2-REG-20261020-CARDIO-1400"
SLOT_1500 = "SLOT-LIVE-V2-REG-20261020-CARDIO-1500"
SLOT_1530 = "SLOT-LIVE-V2-REG-20261020-CARDIO-1530"


class LiveMedicalDemoEndToEndTests(unittest.TestCase):
    def setUp(self):
        # Composition reuses server/process cleanup without inheriting the
        # separate legacy acceptance tests or changing their fixture contract.
        self.harness = h.DemoAgentEndToEndTests()
        self.addCleanup(self.harness.doCleanups)
        original_backend = h.create_backend_application

        def live_backend(data_dir, clock=None):
            return original_backend(
                data_dir, clock=clock,
                medical_data_profile="live-demo-v2", patient_id=h.PATIENT,
            )

        with patch.object(h, "create_backend_application", live_backend):
            self.harness.setUp()
        self.initial_history = deepcopy(self.harness.appointments())
        self.assertEqual(len(self.initial_history), 3)
        self.dispatches = []
        original_call = self.harness.app.mcp_client.call_tool

        def observed_call(name, arguments):
            self.dispatches.append((name, deepcopy(arguments)))
            return original_call(name, arguments)

        self.harness.app.mcp_client.call_tool = observed_call

    def start_draft(self, slot_id=SLOT_1400):
        harness = self.harness
        harness.model.add(
            h.native_call("live-departments", "medical.list_departments", {
                "keyword": "Cardiology", "active_only": True,
            }),
            h.search_call("live-search-P1"),
            h.proposal_call(slot_id, "live-draft-P1"),
        )
        result = harness.say("幫我預約下星期二的心臟科")
        self.assert_draft(result, slot_id)
        return result

    def update_after_three(self):
        harness = self.harness
        harness.model.add(
            h.control("update_constraints", time_constraint={
                "kind": "lower_bound", "time": "15:00", "inclusive": False,
            }),
            h.search_call("live-search-P2"),
            h.proposal_call(SLOT_1530, "live-draft-P2"),
        )
        # Avoid the legacy harness's special CHANGE auto-queue helper.
        result = harness.say("下午三點後先得")
        self.assert_draft(result, SLOT_1530)
        return result

    def step(self, text, action, **fields):
        self.harness.model.add(h.control(action, **fields))
        return self.harness.say(text)

    def assert_draft(self, result, slot_id=None):
        self.assertIsNone(result["receipt"])
        self.assertFalse(any(
            action["event"].get("decision") == "approve"
            for action in result["workspace"]["actions"]
        ))
        self.assertIsNone(result["task"].get("pending_confirmation"))
        self.assertEqual(self.harness.booking_requests(), [])
        if slot_id is not None:
            self.assertEqual(result["task"]["facts"]["selected_slot"]["id"], slot_id)

    def write_dispatches(self):
        return [arguments for name, arguments in self.dispatches
                if name == "medical.create_registration"]

    def search_count(self):
        return sum(name == "medical.search_registration_slots"
                   for name, _ in self.dispatches)

    def test_seven_turn_history_resume_receipt_and_duplicate_approval(self):
        harness = self.harness
        p1 = self.start_draft()
        p2 = self.update_after_three()
        task_id = p1["task"]["task_id"]
        self.assertEqual(p2["task"]["task_id"], task_id)
        self.assertGreater(p2["task"]["facts"]["intent_revision"],
                           p1["task"]["facts"]["intent_revision"])

        queried = self.step("等等，我之前有冇其他預約？", "query_appointments")
        snapshot = queried["task"]["facts"]["appointments_snapshot"]
        self.assertEqual(snapshot["source"], "medical.get_my_appointments")
        self.assertEqual(snapshot["patient_id"], h.PATIENT)
        self.assertTrue(snapshot["request_id"])
        self.assertEqual({record["id"] for record in snapshot["records"]},
                         {record["id"] for record in self.initial_history})
        self.assertEqual({record["status"] for record in snapshot["records"]},
                         {"booked", "confirmed", "cancelled"})
        self.assertEqual(queried["task"]["facts"]["conflict_result"]["status"], "clear")

        answered = self.step("咁會唔會撞時間？", "answer_question")
        self.assertEqual(answered["task"]["facts"]["appointments_snapshot"], snapshot)
        self.assertEqual(answered["task"]["facts"]["conflict_result"]["status"], "clear")
        before_resume = self.search_count()
        resumed = self.step("好，返去頭先個預約", "resume_booking")
        self.assertGreater(self.search_count(), before_resume)
        for result in (queried, answered, resumed):
            self.assertEqual(result["task"]["task_id"], task_id)
            self.assert_draft(result, SLOT_1530)

        before_card = self.search_count()
        card = self.step("就15:30嗰個", "select_slot", target={
            "kind": "time", "time": "15:30",
        })
        self.assertGreater(self.search_count(), before_card)
        self.assertEqual(card["task"]["status"], "awaiting_confirmation")
        self.assertEqual(card["task"]["pending_confirmation"]["appointment"]["date"],
                         "2026-10-20")
        self.assertEqual(card["task"]["pending_confirmation"]["appointment"]["time"], "15:30")
        self.assertEqual(self.write_dispatches(), [])
        self.assertEqual(harness.booking_requests(), [])
        self.assertEqual(harness.appointments(), self.initial_history)

        approval = harness.approval(card)
        completed = harness.interact(approval)
        self.assertEqual(completed["task"]["status"], "completed")
        receipt_id = completed["receipt"]["receipt_id"]
        self.assertRegex(receipt_id, r"^MED-REG-\d+$")
        self.assertEqual(len(self.write_dispatches()), 1)
        self.assertEqual(len(harness.booking_requests()), 1)
        self.assertEqual(harness.booking_requests()[0].body["slot_id"], SLOT_1530)

        records = harness.appointments()
        self.assertEqual(len(records), 4)
        initial_ids = {record["id"] for record in self.initial_history}
        self.assertEqual([record for record in records if record["id"] in initial_ids],
                         self.initial_history)
        booking = next(record for record in records if record["id"] not in initial_ids)
        self.assertEqual(booking["status"], "booked")
        self.assertEqual(booking["patient_id"], h.PATIENT)
        self.assertEqual(booking["slot_id"], SLOT_1530)
        self.assertEqual(booking["start"], "2026-10-20T15:30:00+08:00")
        backend_task = JsonLinesTextRepository(
            harness.data_dir / "medical" / "tasks.txt",
        ).get(booking["task_id"])
        self.assertEqual(backend_task["status"], "completed")
        self.assertEqual(backend_task["appointment_id"], booking["id"])
        response = next(response for request, response in harness.router.responses
                        if request.method == "POST" and request.path.endswith("/registrations"))
        self.assertEqual(response.status, 201)
        self.assertEqual(response.body["receipt"]["reference"], receipt_id)

        repeated = harness.interact(approval)
        self.assertEqual(repeated["receipt"], completed["receipt"])
        self.assertEqual(len(self.write_dispatches()), 1)
        self.assertEqual(len(harness.booking_requests()), 1)
        self.assertEqual(harness.appointments(), records)
        harness.assert_pairing(harness.transcript(completed))
        self.assertEqual(harness.model.responses, [])

    def test_seeded_imaging_overlap_blocks_1500_formal_card(self):
        self.start_draft(SLOT_1500)
        queried = self.step("先查我之前的預約", "query_appointments")
        conflict = queried["task"]["facts"]["conflict_result"]
        self.assertEqual(conflict["status"], "overlap")
        imaging = next(record for record in self.initial_history
                       if record["department"]["id"] == "DEPT-IMAGING")
        self.assertEqual({record["id"] for record in conflict["conflicts"]}, {imaging["id"]})
        card = self.step("就15:00嗰個", "select_slot", target={
            "kind": "time", "time": "15:00",
        })
        self.assert_draft(card, SLOT_1500)
        self.assertEqual(card["task"]["facts"]["conflict_result"]["status"], "overlap")
        self.assertEqual(self.write_dispatches(), [])
        self.assertEqual(self.harness.appointments(), self.initial_history)
        self.assertEqual(self.harness.model.responses, [])

    def test_other_patient_consuming_1530_invalidates_candidate(self):
        harness = self.harness
        self.start_draft()
        p2 = self.update_after_three()
        self.step("等等，我之前有冇其他預約？", "query_appointments")
        status, _ = harness.http_json(
            "POST", f"http://127.0.0.1:{harness.backend.server_port}/mock/medical/v1/registrations",
            {"patient_id": "PAT-OTHER", "department_id": "DEPT-CARDIO",
             "doctor_id": "DOC-002", "slot_id": SLOT_1530, "consent": True},
            {"Authorization": "Bearer mock-user-token", "X-Patient-Id": "PAT-OTHER",
             "Idempotency-Key": "LIVE-V2-TAKE-1530"},
        )
        self.assertEqual(status, 201)
        before_resume = self.search_count()
        resumed = self.step("好，返去頭先個預約", "resume_booking")
        self.assertGreater(self.search_count(), before_resume)
        self.assert_draft(resumed)
        self.assertEqual(resumed["task"]["task_id"], p2["task"]["task_id"])
        self.assertIsNone(resumed["task"]["facts"].get("candidate_id"))
        self.assertEqual(resumed["task"]["facts"].get("response_reason"), "needs_reselection")
        self.assertEqual(self.write_dispatches(), [])
        self.assertEqual(harness.booking_requests(), [])
        other_bookings = harness.booking_requests("PAT-OTHER")
        self.assertEqual(len(other_bookings), 1)
        self.assertEqual(len(harness.appointments()), 4)
        self.assertEqual(harness.model.responses, [])

    def test_production_scripted_client_completes_richer_data_story(self):
        harness = self.harness
        harness.app.demo_workflow.client = ScriptedCardiologyClient()
        turns = [harness.say(text) for text in (
            "幫我預約下星期二的心臟科", "下午三點後先得", "等等，我之前有冇其他預約？",
            "咁會唔會撞時間？", "好，返去頭先個預約", "就15:30嗰個",
        )]
        self.assertEqual(turns[0]["task"]["facts"]["selected_slot"]["id"], SLOT_1400)
        self.assertEqual(turns[1]["task"]["facts"]["selected_slot"]["id"], SLOT_1530)
        self.assertEqual(len(turns[2]["task"]["facts"]["appointments_snapshot"]["records"]), 3)
        self.assertEqual(turns[3]["task"]["facts"]["conflict_result"]["status"], "clear")
        self.assertEqual(turns[-1]["task"]["status"], "awaiting_confirmation")
        self.assertEqual(self.write_dispatches(), [])
        completed = harness.interact(harness.approval(turns[-1]))
        self.assertEqual(completed["task"]["status"], "completed")
        self.assertTrue(completed["receipt"]["receipt_id"])
        self.assertEqual(len(self.write_dispatches()), 1)
        self.assertEqual(len(harness.appointments()), 4)


if __name__ == "__main__":
    unittest.main()
