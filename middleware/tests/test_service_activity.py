import unittest

from middleware.service_activity import project_agent_activity, public_activity, record_tool_events


class ServiceActivityTests(unittest.TestCase):
    def test_private_or_unexecuted_steps_do_not_invent_operations(self):
        trace = [
            {"sequence": 1, "event": "model_decision", "message": "secret"},
            {"sequence": 2, "event": "tool_validated", "tool": "medical.create_appointment"},
            {"sequence": 3, "event": "execution_started", "tool": "medical.create_appointment"},
            {"sequence": 4, "event": "execution_finished", "tool": "unlisted.tool", "ok": True},
        ]
        self.assertEqual(project_agent_activity(trace), [])

    def test_failed_read_is_distinct_from_success_and_ids_are_stable(self):
        trace = [{"sequence": 4, "event": "execution_finished", "tool": "one_account.get_cash_sharing_plan", "ok": False}]
        first = project_agent_activity(trace)
        self.assertEqual(first[0]["id"], "E4")
        self.assertEqual(first[0]["status"], "failed")
        self.assertEqual(first, project_agent_activity(trace))
        self.assertEqual(first[0]["operation"], "cash")

    def test_projection_strips_non_public_fields_and_malformed_operations(self):
        events = public_activity({"service_events": [{"id": "E1", "title": "查詢", "operation": [],
            "arguments": {"patient_id": "secret"}, "authorization": "secret", "model_prompt": "secret"}]})
        self.assertEqual(events, [{"id": "E1", "title": "查詢"}])

    def test_legacy_records_only_executed_allowlisted_operations(self):
        logs = [{"type": "tool_execution", "tool": "medical.list_appointment_services", "ok": True},
                {"type": "workflow_called"}, {"type": "tool_execution", "tool": "private.tool", "ok": True}]
        self.assertEqual(len(record_tool_events(logs, offset=3)), 1)
        self.assertEqual(record_tool_events(logs, offset=3)[0]["id"], "E4")
