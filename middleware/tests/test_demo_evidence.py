import unittest
from middleware.demo_evidence import constraint_text, record_service_events
from middleware.interaction_delivery import WorkspaceProjector
from middleware.tests.test_interaction_delivery import result_for

class DemoEvidenceTests(unittest.TestCase):
    def events(self, facts=None, logs=None, previous=None, **options):
        return record_service_events(facts or {}, logs or [], previous or {},
            phase=options.pop("phase", "draft"), confirmation=options.pop("confirmation", None),
            receipt=options.pop("receipt", None), recovery=options.pop("recovery", None),
            at="2026-10-14T10:00:00+08:00", offset=options.pop("offset", 0))

    def test_time_boundaries_are_explicit_and_not_conflated(self):
        inclusive=constraint_text({"kind":"lower_bound","time":"15:00","inclusive":True})
        exclusive=constraint_text({"kind":"lower_bound","time":"15:00","inclusive":False})
        self.assertIn("包含該時間", inclusive)
        self.assertIn("不包含該時間", exclusive)
        self.assertNotEqual(inclusive, exclusive)
        self.assertEqual(constraint_text({"kind":"exact","time":"15:00"}),"指定 15:00")

    def test_no_tools_or_candidate_does_not_invent_a_workflow(self):
        events,_=self.events()
        self.assertEqual(events,[])

    def test_only_executed_allowlisted_operations_are_displayed(self):
        events,_=self.events(logs=[{"type":"tool_execution","tool":"medical.search_registration_slots","ok":False,"call_id":"SECRET"}, {"type":"tool_execution","tool":"invented.tool","ok":True}])
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["status"],"failed")
        self.assertNotIn("SECRET",str(events))
        self.assertNotIn("invented.tool",str(events))

    def test_revisions_revoke_previous_approval_in_the_evidence(self):
        events,_=self.events({"intent_revision":2,"time_constraint":{"kind":"exact","time":"14:00"}}, previous={"revision":1,"confirmation":"OLD"})
        self.assertEqual([e["kind"] for e in events],["constraints_updated","approval_invalidated"])

    def test_receipt_evidence_is_not_inferred_from_a_successful_write_reply(self):
        events,_=self.events(logs=[{"type":"tool_execution","tool":"medical.create_registration","ok":True}])
        self.assertFalse(any(e["kind"]=="receipt_verified" for e in events))
        events,previous=self.events(receipt={"receipt_id":"MED-REG-1"})
        self.assertEqual(events[-1]["kind"],"receipt_verified")
        repeated,_=self.events(previous=previous,receipt={"receipt_id":"MED-REG-1"})
        self.assertEqual(repeated,[])

    def test_projection_whitelists_evidence_and_exposes_mode_and_constraint(self):
        result=result_for("select_slot",facts={"engine":"demo_agent","model_mode":"scripted","intent_revision":2,
            "time_constraint":{"kind":"lower_bound","time":"15:00","inclusive":False},
            "service_events":[{"id":"E1","title":"查詢時段","detail":"已收到回覆","authorization":"SECRET","call_id":"INTERNAL"}]})
        projection=WorkspaceProjector.project(result)
        self.assertNotIn("SECRET",str(projection))
        self.assertNotIn("INTERNAL",str(projection))
        self.assertIn("腳本模型示範",str(projection["context"]))
        self.assertIn("不包含該時間",str(projection["context"]))
        self.assertIn("第 2 版需求",str(projection["context"]))

    def test_replaced_draft_and_selection_reference_have_observable_evidence(self):
        events,_=self.events({"candidate_id":"P2","selected_slot":{"start":"2026-10-20T15:30:00+08:00"}},
            logs=[{"type":"selection_resolved","kind":"ordinal","ordinal":2}], previous={"candidate":"P1"})
        kinds=[e["kind"] for e in events]
        self.assertIn("draft_invalidated",kinds)
        self.assertIn("selection_resolved",kinds)
        self.assertIn("第 2 個",str(events))
        self.assertIn("尚未提交",str(events))

    def test_conflict_details_are_readable_without_internal_snapshot_ids(self):
        result=result_for("select_slot",facts={"candidate_id":"P2","conflict_result":{"status":"unknown","snapshot_request_id":"SECRET-INTERNAL","candidate_id":"PRIVATE-SLOT"}})
        projection=WorkspaceProjector.project(result)
        self.assertIn("尚未能排除撞期",str(projection))
        self.assertNotIn("SECRET-INTERNAL",str(projection))
        self.assertNotIn("PRIVATE-SLOT",str(projection))
