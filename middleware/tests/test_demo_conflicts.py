"""Round 2 conflict rules use real instants and half-open intervals."""

from copy import deepcopy
import unittest

from middleware.demo_medical_workflow import evaluate_conflicts
from middleware.demo_medical_workflow import DemoMedicalWorkflow
from middleware.demo_model import ScriptedCardiologyClient
from middleware.contracts import ToolExecutionResult
from middleware.tests.test_demo_medical_workflow import MemoryPipeline, NOW, REQUEST, envelope
from MCP.registry import build_registry
from mock_backends.core.clock import FixedClock


class DemoConflictTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {"id": "P2", "start": "2026-10-20T15:30:00+08:00", "end": "2026-10-20T15:45:00+08:00"}

    def record(self, start="2026-10-20T15:00:00+08:00", end="2026-10-20T15:30:00+08:00", status="booked"):
        return {"id": "APT-EXISTING", "start": start, "end": end, "status": status}

    def evaluate(self, records, candidate=None):
        return evaluate_conflicts(candidate or self.candidate, {"records": records, "request_id": "REQ-QUERY"})

    def test_endpoint_contact_on_either_side_is_clear(self):
        for record in (self.record(), self.record("2026-10-20T15:45:00+08:00", "2026-10-20T16:00:00+08:00")):
            with self.subTest(record=record):
                result = self.evaluate([record])
                self.assertEqual(result["status"], "clear")
                self.assertEqual(result["conflicts"], [])
                self.assertEqual(result["candidate_id"], "P2")
                self.assertEqual(result["snapshot_request_id"], "REQ-QUERY")

    def test_overlap_is_identified_for_booked_and_confirmed(self):
        for status in ("booked", "confirmed"):
            record = self.record("2026-10-20T15:15:00+08:00", "2026-10-20T15:45:00+08:00", status)
            result = self.evaluate([record])
            self.assertEqual(result["status"], "overlap")
            self.assertEqual(result["conflicts"], [{"id": record["id"], "start": record["start"], "end": record["end"]}])

    def test_containing_equal_and_contained_intervals_overlap(self):
        for start, end in (("15:00", "16:00"), ("15:30", "15:45"), ("15:35", "15:40")):
            with self.subTest(start=start, end=end):
                self.assertEqual(self.evaluate([self.record(f"2026-10-20T{start}:00+08:00", f"2026-10-20T{end}:00+08:00")])["status"], "overlap")

    def test_offsets_representing_same_instants_overlap(self):
        self.assertEqual(self.evaluate([self.record("2026-10-20T07:30:00Z", "2026-10-20T09:45:00+02:00")])["status"], "overlap")

    def test_cross_midnight_uses_dates(self):
        candidate = {"id": "P2", "start": "2026-10-20T23:50:00+08:00", "end": "2026-10-21T00:10:00+08:00"}
        self.assertEqual(self.evaluate([self.record("2026-10-21T00:00:00+08:00", "2026-10-21T00:30:00+08:00")], candidate)["status"], "overlap")
        self.assertEqual(self.evaluate([self.record("2026-10-21T00:10:00+08:00", "2026-10-21T00:30:00+08:00")], candidate)["status"], "clear")

    def test_different_dates_do_not_overlap(self):
        self.assertEqual(self.evaluate([self.record("2026-10-21T15:30:00+08:00", "2026-10-21T15:45:00+08:00")])["status"], "clear")

    def test_cancelled_records_do_not_block_even_with_missing_times(self):
        self.assertEqual(self.evaluate([{"id": "C1", "status": "cancelled"}, {"id": "C2", "status": "canceled"}])["status"], "clear")

    def test_missing_invalid_or_naive_appointment_times_are_unknown(self):
        variants = [self.record(), self.record(), self.record(), self.record(), self.record()]
        variants[0].pop("end")
        variants[1]["start"] = "2026-10-20T15:00:00"
        variants[2]["end"] = "not a timestamp"
        variants[3]["end"] = variants[3]["start"]
        variants[4]["start"] = None
        for record in variants:
            with self.subTest(record=record):
                self.assertEqual(self.evaluate([record])["status"], "unknown")

    def test_unknown_status_is_unknown_even_if_clock_time_is_distant(self):
        for status in ("pending", "waitlisted", None):
            self.assertEqual(self.evaluate([self.record(status=status)])["status"], "unknown")

    def test_empty_successful_snapshot_clear_failed_or_missing_snapshot_unknown(self):
        self.assertEqual(self.evaluate([])["status"], "clear")
        for snapshot in (None, {}, {"records": None}, {"records": "bad"}):
            self.assertEqual(evaluate_conflicts(self.candidate, snapshot)["status"], "unknown")

    def test_invalid_candidate_interval_is_unknown(self):
        for key, value in (("start", "2026-10-20T15:30:00"), ("end", None), ("end", "2026-10-20T15:00:00+08:00")):
            candidate = deepcopy(self.candidate)
            candidate[key] = value
            self.assertEqual(self.evaluate([], candidate)["status"], "unknown")

    def test_known_overlap_still_blocks_when_another_record_is_unknown(self):
        records = [self.record("2026-10-20T15:35:00+08:00", "2026-10-20T15:50:00+08:00"), self.record(status="pending")]
        before = deepcopy(records)
        self.assertEqual(self.evaluate(records)["status"], "overlap")
        self.assertEqual(records, before)

    def test_incomplete_paginated_query_cannot_become_clear_or_issue_approval(self):
        for metadata in ({"has_next": True, "total": 1, "page": 1}, {"total": 2, "page": 1}, {"total": 0, "page": 2}):
            with self.subTest(metadata=metadata):
                class PaginatedPipeline(MemoryPipeline):
                    def dispatch(self, call):
                        if call.name == "medical.get_my_appointments":
                            self.calls.append(call)
                            return ToolExecutionResult(call.name, call.step_id, True, "REQ-PAGE", data={"data": [], "meta": metadata})
                        return super().dispatch(call)
                pipeline = PaginatedPipeline()
                workflow = DemoMedicalWorkflow(pipeline, "PAT-UNIT", "Bearer test", registry=build_registry(), client=ScriptedCardiologyClient(), clock=FixedClock(NOW))
                task, draft, _ = workflow.start(envelope({"type": "user_utterance", "content": REQUEST}))
                task, inquiry, _ = workflow.handle(task, envelope({"type": "user_utterance", "content": "check my appointments"}))
                self.assertEqual(inquiry.facts["conflict_result"]["status"], "unknown")
                self.assertEqual(inquiry.facts["candidate_id"], draft.facts["candidate_id"])
                task, _, _ = workflow.handle(task, envelope({"type": "user_utterance", "content": "return to booking"}))
                _, selection, _ = workflow.handle(task, envelope({"type": "user_utterance", "content": "select current slot"}))
                self.assertIsNone(selection.confirmation)
                self.assertFalse(any(call.name == "medical.create_registration" for call in pipeline.calls))


if __name__ == "__main__":
    unittest.main()
