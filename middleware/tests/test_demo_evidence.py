import unittest
from middleware.demo_evidence import constraint_text, record_service_events, record_tool_events
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

    def test_observed_tools_have_distinct_stable_operations(self):
        tools = ["medical.list_departments", "medical.search_registration_slots",
                 "medical.get_my_appointments", "medical.create_registration"]
        events, _ = self.events(logs=[{"type": "tool_execution", "tool": tool, "ok": True} for tool in tools])
        self.assertEqual([event["operation"] for event in events],
                         ["departments", "slots", "appointments", "booking"])
        self.assertEqual([event["kind"] for event in events],
                         ["service_lookup", "service_lookup", "service_lookup", "booking_submitted"])
        failed, _ = self.events(logs=[{"type": "tool_execution", "tool": tools[1], "ok": False}])
        self.assertEqual(failed[0]["operation"], "slots")
        self.assertEqual(failed[0]["status"], "failed")
        changed, _ = self.events({"intent_revision": 2}, previous={"revision": 1})
        self.assertNotIn("operation", changed[0])

    def test_projection_preserves_only_allowlisted_operation_values(self):
        allowed = ["departments", "slots", "appointments", "booking", "services", "cash"]
        operations = allowed + ["confirm_automatically",
                      {"authorization": "NESTED-SECRET"}, ["slots"], None]
        events = [{"id": f"E{i}", "title": "服務回覆", "operation": operation,
                   "authorization": "RAW-SECRET", "result": {"call_id": "PRIVATE-CALL"}}
                  for i, operation in enumerate(operations)]
        projection = WorkspaceProjector.project(result_for("select_slot", facts={"service_events": events}))
        public = projection["activity"]
        self.assertEqual([event.get("operation") for event in public[:len(allowed)]], allowed)
        self.assertTrue(all("operation" not in event for event in public[len(allowed):]))
        self.assertNotIn("confirm_automatically", str(public))
        self.assertNotIn("SECRET", str(public))
        self.assertNotIn("PRIVATE-CALL", str(public))
        self.assertTrue(all(set(event) <= {"id", "title", "operation"} for event in public))

    def test_common_tool_evidence_does_not_invent_workflow_milestones(self):
        tools = ["medical.list_appointment_services", "medical.search_appointment_slots",
                 "medical.create_appointment", "one_account.get_cash_sharing_plan"]
        logs = [{"type": "tool_execution", "tool": tool, "ok": True,
                 "authorization": "SECRET", "result": {"token": "PRIVATE"}} for tool in tools]
        logs.extend([{"type": "tool_selected", "tool": tools[0]},
                     {"type": "tool_execution", "tool": "unknown.tool", "ok": True}, None])
        events = record_tool_events(logs, at="2026-10-14T00:00:00Z", offset=5)
        self.assertEqual([event["operation"] for event in events], ["services", "slots", "booking", "cash"])
        self.assertEqual([event["id"] for event in events], ["E6", "E7", "E8", "E9"])
        self.assertEqual({event["kind"] for event in events}, {"service_lookup", "booking_submitted"})
        self.assertNotIn("SECRET", str(events))
        self.assertNotIn("PRIVATE", str(events))

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
        self.assertNotIn("腳本模型示範",str(projection["context"]))
        self.assertEqual(result.facts["model_mode"],"scripted")
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
