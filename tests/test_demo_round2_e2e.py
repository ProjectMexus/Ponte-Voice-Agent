"""Round 2 acceptance: only model decisions are scripted; all tools use MCP/HTTP."""
from datetime import timedelta
import unittest
from concurrent.futures import ThreadPoolExecutor
import tests.test_demo_agent_e2e as h
from middleware.mcp_client import McpClientError
from mock_backends.core.persistence import JsonLinesTextRepository


class DemoRound2EndToEndTests(unittest.TestCase):
    def seed_appointment(self, *, start="15:00", end="15:30", status="booked", missing_end=False):
        record = {"id": "APT-EXISTING", "patient_id": h.PATIENT,
                  "patient": {"id": h.PATIENT}, "status": status,
                  "start": f"2026-10-20T{start}:00+08:00",
                  "end": f"2026-10-20T{end}:00+08:00",
                  "department": {"id": "DEPT-OTHER", "name": "既有預約"}}
        if missing_end:
            record.pop("end")
        JsonLinesTextRepository(self.data_dir / "medical" / "appointments.txt").insert(record)

    def step(self, text, action):
        self.model.add(h.control(action))
        return self.say(text)

    def drafts(self):
        self.model.add(*h.first_proposal_script())
        p1 = self.say("幫我預約下星期二的心臟科")
        self.assert_draft(p1, "P1", "14:00")
        self.model.add(h.search_call("search-P2"), h.proposal_call(h.SLOT_1530, "draft-P2"))
        p2 = self.say(h.CHANGE)
        self.assert_draft(p2, "P2", "15:30")
        self.assertGreater(p2["task"]["facts"]["intent_revision"], p1["task"]["facts"]["intent_revision"])
        return p1, p2

    def assert_draft(self, result, candidate=None, time=None):
        self.assertIsNone(result["receipt"])
        self.assertFalse(any(a["event"].get("decision") == "approve" for a in result["workspace"]["actions"]))
        self.assertEqual(self.booking_requests(), [])
        if candidate:
            self.assertEqual(result["task"]["facts"]["candidate_id"], candidate)
        if time:
            self.assertEqual(result["task"]["facts"]["selected_slot"]["start"][11:16], time)
        self.assert_pairing(self.transcript(result))

    def inquiry_resume(self):
        _, p2 = self.drafts()
        queried = self.step("等等，我之前有冇其他預約？", "query_appointments")
        answered = self.step("咁會唔會撞時間？", "answer_question")
        resumed = self.step("好，返去頭先個預約", "resume_booking")
        for result in (queried, answered, resumed):
            self.assertEqual(result["task"]["task_id"], p2["task"]["task_id"])
            self.assertEqual(result["task"]["facts"]["intent_revision"], p2["task"]["facts"]["intent_revision"])
            self.assert_draft(result, "P2", "15:30")
        return queried, answered, resumed

    def test_seven_turn_boundary_story_and_duplicate_approve(self):
        self.seed_appointment()
        queried, answered, resumed = self.inquiry_resume()
        snapshot = queried["task"]["facts"]["appointments_snapshot"]
        self.assertEqual(snapshot["source"], "medical.get_my_appointments")
        self.assertEqual(snapshot["patient_id"], h.PATIENT)
        self.assertTrue(snapshot["request_id"])
        query_calls = [call for message in self.transcript(queried) for call in message.get("tool_calls", [])
                       if call["function"]["name"] == "medical.get_my_appointments"]
        self.assertEqual(len(query_calls), 1)
        self.assertEqual(query_calls[0]["function"]["arguments"], "{}")
        self.assertEqual(answered["task"]["facts"]["appointments_snapshot"], snapshot)
        self.assertEqual(answered["task"]["facts"]["conflict_result"]["status"], "clear")
        paths = [r.path for r in self.router.requests]
        self.assertTrue(any(p.endswith("/appointments") for p in paths))
        searches = [r for r in self.router.requests if "registration-slots" in r.path or "registration_slots" in r.path]
        self.assertGreaterEqual(len(searches), 3)
        selected = self.step("就15:30嗰個", "select_slot")
        self.assertEqual(self.booking_requests(), [])
        self.assertEqual(selected["task"]["pending_confirmation"]["candidate_id"], "P2")
        action = self.approval(selected)
        self.assertNotEqual(action["confirmation_id"], "P2")
        booked = self.interact(action)
        self.assertEqual(booked["task"]["status"], "completed")
        self.assertTrue(booked["receipt"]["receipt_id"].startswith("MED-REG-"))
        self.assertEqual(self.booking_requests()[0].body["slot_id"], h.SLOT_1530)
        self.assertEqual(len(self.booking_requests()), 1)
        repeated = self.interact(action)
        self.assertEqual(repeated["receipt"], booked["receipt"])
        self.assertEqual(len(self.booking_requests()), 1)
        self.assertEqual(len(self.appointments()), 2, "Existing appointments must be preserved")
        self.assert_pairing(self.transcript(booked))
        for messages, _ in self.model.requests:
            self.assert_pairing(messages)

    def test_rehearsal_script_uses_production_scripted_model_and_real_stack(self):
        from middleware.demo_model import ScriptedCardiologyClient
        from scripts.demo_cardiology import rehearse
        self.seed_appointment()
        self.app.demo_workflow.client = ScriptedCardiologyClient()
        completed = rehearse(f"http://127.0.0.1:{self.middleware.server_port}")
        self.assertEqual(completed["task"]["status"], "completed")
        self.assertEqual(len(self.booking_requests()), 1)
        self.assertEqual(len(self.appointments()), 2)
        self.assert_pairing(self.transcript(completed))

    def test_overlap_blocks_formal_card(self):
        self.seed_appointment(start="15:15", end="15:45")
        queried, _, _ = self.inquiry_resume()
        self.assertEqual(queried["task"]["facts"]["conflict_result"]["status"], "overlap")
        self.assert_draft(self.step("就15:30嗰個", "select_slot"))

    def test_missing_end_blocks_formal_card(self):
        self.seed_appointment(missing_end=True)
        queried, _, _ = self.inquiry_resume()
        self.assertEqual(queried["task"]["facts"]["conflict_result"]["status"], "unknown")
        self.assert_draft(self.step("就15:30嗰個", "select_slot"))

    def test_query_failure_preserves_candidate_and_blocks_confirmation(self):
        _, p2 = self.drafts()
        original = self.app.mcp_client.call_tool
        def fail_query(name, arguments):
            if name == "medical.get_my_appointments":
                raise McpClientError("MCP_TIMEOUT", "Injected query failure", status=504, retryable=True)
            return original(name, arguments)
        self.app.mcp_client.call_tool = fail_query
        queried = self.step("查下我仲有咩預約", "query_appointments")
        self.assert_draft(queried, "P2", "15:30")
        self.assertEqual(queried["task"]["facts"]["conflict_result"]["status"], "unknown")
        self.assertEqual(queried["task"]["task_id"], p2["task"]["task_id"])
        self.step("返回剛才掛號", "resume_booking")
        self.assert_draft(self.step("揀15:30", "select_slot"))

    def test_query_revokes_old_card_and_resume_requires_new_selection(self):
        _, p2 = self.drafts()
        selected = self.step("揀15:30", "select_slot")
        old = self.approval(selected)
        self.step("我有其他預約嗎", "query_appointments")
        rejected = self.interact(old, allow_rejection=True)
        self.assertIsNone(rejected.get("receipt"))
        resumed = self.step("返回掛號", "resume_booking")
        self.assert_draft(resumed, "P2")
        fresh = self.step("揀15:30", "select_slot")
        self.assertNotEqual(old["confirmation_id"], self.approval(fresh)["confirmation_id"])
        self.assertEqual(self.booking_requests(), [])

    def test_stale_approval_refreshes_then_requires_second_click(self):
        self.drafts()
        selected = self.step("揀15:30", "select_slot")
        old = self.approval(selected)
        self.clock._value += timedelta(seconds=61)
        refreshed = self.interact(old)
        self.assertEqual(self.booking_requests(), [])
        new = self.approval(refreshed)
        self.assertNotEqual(new["confirmation_id"], old["confirmation_id"])
        self.interact(old, allow_rejection=True)
        self.assertEqual(self.booking_requests(), [])
        completed = self.interact(new)
        self.assertEqual(completed["task"]["status"], "completed")
        self.assertEqual(len(self.booking_requests()), 1)

    def test_expired_candidate_resume_does_not_extend_p2(self):
        self.drafts()
        self.step("查下其他預約", "query_appointments")
        self.clock._value += timedelta(seconds=301)
        resumed = self.step("返回掛號", "resume_booking")
        self.assert_draft(resumed)
        self.assertNotEqual(resumed["task"]["facts"].get("candidate_id"), "P2")

    def test_taken_candidate_resume_never_swaps_slot(self):
        self.drafts()
        self.step("查下其他預約", "query_appointments")
        status, _ = self.http_json("POST", f"http://127.0.0.1:{self.backend.server_port}/mock/medical/v1/registrations", {
            "patient_id": "PAT-OTHER", "department_id": "DEPT-CARDIO", "doctor_id": "DOC-002",
            "slot_id": h.SLOT_1530, "consent": True,
        }, {"Authorization": "Bearer mock-user-token", "X-Patient-Id": "PAT-OTHER", "Idempotency-Key": "TAKE-P2"})
        self.assertEqual(status, 201)
        resumed = self.step("返回掛號", "resume_booking")
        self.assert_draft(resumed)
        self.assertNotEqual(resumed["task"]["facts"].get("candidate_id"), "P2")

    def test_query_winning_session_lock_revokes_queued_approval(self):
        self.drafts()
        card = self.step("揀15:30", "select_slot")
        self.model.add(h.control("query_appointments"))
        self.model.block_action = "query_appointments"
        with ThreadPoolExecutor(max_workers=2) as workers:
            query = workers.submit(self.say, "我仲有其他預約嗎")
            self.assertTrue(self.model.entered.wait(5))
            approve = workers.submit(self.interact, self.approval(card), allow_rejection=True)
            self.model.release.set()
            queried = query.result(timeout=10)
            stale = approve.result(timeout=10)
        self.assert_draft(queried, "P2")
        self.assertIsNone(stale.get("receipt"))
        self.assertEqual(self.booking_requests(), [])

    def test_approve_winning_session_lock_cannot_be_cancelled_by_query(self):
        self.drafts()
        card = self.step("揀15:30", "select_slot")
        self.router.block_registration = True
        with ThreadPoolExecutor(max_workers=2) as workers:
            approve = workers.submit(self.interact, self.approval(card))
            self.assertTrue(self.router.entered.wait(5))
            query = workers.submit(self.say, "等等，我有其他預約嗎")
            self.router.release.set()
            completed = approve.result(timeout=10)
            later = query.result(timeout=10)
        self.assertEqual(completed["task"]["status"], "completed")
        self.assertEqual(self.app.demo_workflow._states[completed["task"]["task_id"]].task["status"], "completed")
        self.assertEqual(self.appointments()[0]["status"], "booked")
        self.assertNotEqual(later["task"]["status"], "cancelled")
        self.assertEqual(len(self.booking_requests()), 1)
        self.assert_pairing(self.transcript(completed))


# Reuse the real HTTP/MCP harness without inheriting its separate regression cases.
for _name, _value in vars(h.DemoAgentEndToEndTests).items():
    if callable(_value) and not _name.startswith("test_") and _name not in vars(DemoRound2EndToEndTests):
        setattr(DemoRound2EndToEndTests, _name, _value)

if __name__ == "__main__":
    unittest.main()
