"""Focused pilot regressions; immutable evaluation cases remain untouched."""
from copy import deepcopy
import unittest
from middleware.agent import AgentProtocolError
from middleware.tests import test_demo_medical_workflow as harness

REQUEST = harness.REQUEST
envelope = harness.envelope


class PilotRegressionTests(unittest.TestCase):
    setUp = harness.DemoMedicalWorkflowTests.setUp
    start = harness.DemoMedicalWorkflowTests.start
    approval = staticmethod(harness.DemoMedicalWorkflowTests.approval)
    writes = harness.DemoMedicalWorkflowTests.writes

    def test_published_second_option_can_be_selected_without_an_automatic_draft(self):
        task, _, _ = self.workflow.start(envelope({"type": "user_utterance", "content": REQUEST}))
        state = self.workflow._states[task["task_id"]]
        self.workflow._clear_candidate(state)
        self.assertIsNotNone(state.presentation)
        task, selected, _ = self.say(task, "選第二個")
        self.assertIsNotNone(selected.confirmation)
        self.assertEqual(selected.confirmation["appointment"]["time"], "15:30")
        self.assertEqual(self.writes(), [])

    def test_selection_without_published_options_cannot_issue_confirmation(self):
        task, _, _ = self.workflow.start(envelope({"type": "user_utterance", "content": REQUEST}))
        state = self.workflow._states[task["task_id"]]
        self.workflow._clear_candidate(state)
        self.workflow._clear_options(state)
        task, selected, _ = self.say(task, "選第二個")
        self.assertIsNone(selected.confirmation)
        self.assertFalse(selected.allowed_actions)
        self.assertEqual(self.writes(), [])

    def test_model_cannot_weaken_explicit_english_after_boundary(self):
        from types import SimpleNamespace
        task, _, _ = self.workflow.start(envelope({"type": "user_utterance", "content": REQUEST}))
        original = self.workflow.client.complete
        attempts = []
        def complete(messages, **options):
            if options.get("demo_control") and not attempts:
                attempts.append(True)
                return {"action": "update_constraints", "time_constraint": {
                    "kind": "lower_bound", "time": "15:00", "inclusive": True}}
            return original(messages, **options)
        self.workflow.client = SimpleNamespace(complete=complete)
        task, revised, _ = self.say(task, "Only after 3 PM")
        self.assertEqual(revised.facts["time_constraint"], {
            "kind": "lower_bound", "time": "15:00", "inclusive": False})
        self.assertEqual(revised.facts["selected_slot"]["start"][11:16], "15:30")
        self.assertEqual(self.writes(), [])

    def test_repeated_model_boundary_conflict_pauses_without_submission(self):
        from types import SimpleNamespace
        task, _, _ = self.workflow.start(envelope({"type": "user_utterance", "content": REQUEST}))
        self.workflow.client = SimpleNamespace(complete=lambda *a, **k: {
            "action": "update_constraints", "time_constraint": {
                "kind": "lower_bound", "time": "15:00", "inclusive": True}})
        task, paused, _ = self.say(task, "Only after 3 PM")
        self.assertIsNone(paused.confirmation)
        self.assertFalse(paused.allowed_actions)
        self.assertEqual(self.writes(), [])
    def say(self, task, content):
        return self.workflow.handle(task, envelope({"type": "user_utterance", "content": content}))

    def test_formal_card_ambiguous_then_reselect_issues_new_card(self):
        task, card, _ = self.start()
        old = self.approval(card)
        task, ambiguous, _ = self.say(task, "maybe, I am not sure")
        self.assertEqual(ambiguous.facts["phase"], "awaiting_selection")
        self.assertFalse(ambiguous.allowed_actions)
        self.assertIsNone(ambiguous.confirmation)
        task, replacement, _ = self.say(task, "select current slot")
        self.assertNotEqual(self.approval(replacement)["confirmation_id"], old["confirmation_id"])
        self.assertEqual(self.writes(), [])

    def test_inclusive_and_exclusive_boundaries(self):
        for phrase, expected in [("change to >=15:30", "15:30"), ("change to after 15:00", "15:30"), ("change to exact 14:00", "14:00")]:
            with self.subTest(phrase=phrase):
                self.setUp()
                task, _, _ = self.workflow.start(envelope({"type": "user_utterance", "content": REQUEST}))
                task, draft, _ = self.say(task, phrase)
                self.assertEqual(draft.facts["selected_slot"]["start"][11:16], expected)
                self.assertEqual(self.writes(), [])

    def test_exact_reversal_replaces_lower_bound_and_revokes_old_card(self):
        task, _, _ = self.workflow.start(envelope({"type": "user_utterance", "content": REQUEST}))
        task, draft, _ = self.say(task, "change to after 15:00")
        self.assertEqual(draft.facts["selected_slot"]["start"][11:16], "15:30")
        task, card, _ = self.say(task, "select current slot")
        old = self.approval(card)
        task, revised, _ = self.say(task, "change to exact 14:00")
        self.assertEqual(revised.facts["time_constraint"], {"kind": "exact", "time": "14:00"})
        self.assertEqual(revised.facts["selected_slot"]["start"][11:16], "14:00")
        self.assertFalse(revised.allowed_actions)
        self.assertGreater(revised.facts["intent_revision"], card.facts["intent_revision"])
        try:
            self.workflow.handle(task, envelope(old))
        except ValueError:
            pass
        self.assertEqual(self.writes(), [])

    def test_ordinal_selects_displayed_second_option(self):
        task, draft, _ = self.workflow.start(envelope({"type": "user_utterance", "content": REQUEST}))
        self.assertEqual(draft.facts["selected_slot"]["start"][11:16], "14:00")
        task, card, _ = self.say(task, "選第二個")
        self.assertIsNotNone(card.confirmation)
        self.assertEqual(card.facts["selected_slot"]["start"][11:16], "15:30")
        self.assertEqual(self.writes(), [])

    def test_fresh_cached_slot_loss_cannot_issue_or_click_old_card(self):
        task, card, _ = self.start()
        old = deepcopy(self.approval(card))
        selected_id = card.facts["selected_slot"]["id"]
        slot = next(item for item in self.pipeline.slots if item["id"] == selected_id)
        slot.update(remaining=0, status="busy")
        task, result, _ = self.say(task, "select current slot")
        self.assertIsNone(result.confirmation)
        self.assertFalse(result.allowed_actions)
        try:
            self.workflow.handle(task, envelope(old))
        except ValueError:
            pass
        self.assertEqual(self.writes(), [])

    def test_search_session_default_and_explicit_conflict(self):
        task, _, _ = self.workflow.start(envelope({'type':'user_utterance','content':REQUEST}))
        state = self.workflow._states[task['task_id']]
        args = {'department_id':'DEPT-CARDIO','date':state.date}
        self.workflow._validate_arguments(state,'medical.search_registration_slots',args)
        self.assertEqual(args['session'],'afternoon')
        with self.assertRaises(AgentProtocolError):
            self.workflow._validate_arguments(state,'medical.search_registration_slots',{**args,'session':'morning'})

    def test_query_read_failure_cannot_issue_card(self):
        from middleware.contracts import ToolExecutionResult
        task, _, _ = self.workflow.start(envelope({'type':'user_utterance','content':REQUEST}))
        dispatch = self.pipeline.dispatch
        def fail_query(call):
            if call.name == 'medical.get_my_appointments':
                return ToolExecutionResult(call.name,call.step_id,False,'FAILED',error={'code':'UNAVAILABLE'})
            return dispatch(call)
        self.pipeline.dispatch = fail_query
        task, result, _ = self.say(task,'select current slot')
        self.assertIsNone(result.confirmation)
        self.assertFalse(result.allowed_actions)
        self.assertEqual(result.facts['conflict_result']['status'],'unknown')
        self.assertEqual(self.writes(),[])

    def test_resume_read_failure_clears_candidate_and_approval(self):
        from middleware.contracts import ToolExecutionResult
        task, card, _ = self.start()
        old = self.approval(card)
        dispatch = self.pipeline.dispatch
        def fail_search(call):
            if call.name == 'medical.search_registration_slots':
                return ToolExecutionResult(call.name,call.step_id,False,'FAILED',error={'code':'UNAVAILABLE'})
            return dispatch(call)
        self.pipeline.dispatch = fail_search
        task, result, _ = self.say(task,'resume booking')
        self.assertIsNone(result.confirmation)
        self.assertFalse(result.allowed_actions)
        self.assertNotIn('candidate_id',result.facts)
        self.assertEqual(result.facts['slots'],[])
        self.assertNotIn('options_presentation',result.facts)
        self.assertEqual(result.facts['response_reason'],'needs_reselection')
        self.assertIn('未能重新核實',result.facts['response_message'])
        with self.assertRaises(ValueError): self.workflow.handle(task,envelope(old))
        self.assertEqual(self.writes(),[])

    def test_control_schema_repair_bounded_once(self):
        task, _, _ = self.workflow.start(envelope({'type':'user_utterance','content':REQUEST}))
        class Client:
            calls = 0
            def complete(inner,*args,**kwargs):
                inner.calls += 1
                return {'action':'medical_get_my_appointments'}
        client = Client()
        self.workflow.client = client
        task, result, _ = self.say(task,'look at appointments')
        self.assertEqual(client.calls,2)
        self.assertEqual(result.facts['response_kind'],'clarification')
        self.assertEqual(self.writes(),[])


    def test_malformed_target_repairs_once_before_formal_card(self):
        task, _, _ = self.workflow.start(envelope({'type':'user_utterance','content':REQUEST}))
        class Client:
            def __init__(inner): inner.requests = []
            def complete(inner, messages, **options):
                inner.requests.append(deepcopy(messages))
                if len(inner.requests) == 1:
                    return {'action':'select_slot','target':{'kind':'ordinal','ordinal':True,'presentation_id':'x'}}
                return {'action':'select_slot','target':{'kind':'time','time':'15:30'}}
        client = Client()
        self.workflow.client = client
        task, card, _ = self.say(task,'select the later option')
        self.assertEqual(len(client.requests),2)
        self.assertIn('Invalid control schema or phase', client.requests[1][0]['content'])
        self.assertEqual(card.facts['selected_slot']['start'][11:16],'15:30')
        self.assertIsNotNone(card.confirmation)
        self.assertEqual(self.writes(),[])

    def test_stale_presentation_clarifies_without_reinterpreting_ordinal(self):
        task, first, _ = self.workflow.start(envelope({'type':'user_utterance','content':REQUEST}))
        original_presentation = first.facts['options_presentation']['presentation_id']
        task, revised, _ = self.say(task,'change to after 15:00')
        current_id = revised.facts['candidate_id']
        self.assertNotEqual(revised.facts['options_presentation']['presentation_id'],original_presentation)
        class Client:
            calls = 0
            def complete(inner,*args,**kwargs):
                inner.calls += 1
                return {'action':'select_slot','target':{'kind':'ordinal','ordinal':1,'presentation_id':original_presentation}}
        client = Client()
        self.workflow.client = client
        reads_before = len(self.pipeline.calls)
        task, result, _ = self.say(task,'the first option from the old list')
        self.assertEqual(client.calls,1, 'valid schema with stale reference needs clarification, not repair')
        self.assertEqual(result.facts['response_kind'],'clarification')
        self.assertEqual(result.facts['candidate_id'],current_id)
        self.assertEqual(result.facts['selected_slot']['start'][11:16],'15:30')
        self.assertEqual(len(self.pipeline.calls),reads_before)
        self.assertIsNone(result.confirmation)
        self.assertFalse(result.allowed_actions)
        self.assertEqual(self.writes(),[])

    def test_cancel_response_drops_previous_approval_message(self):
        task, card, _ = self.start()
        reject = next(action['event'] for action in card.allowed_actions if action['event']['decision'] == 'reject')
        task, result, _ = self.workflow.handle(task,envelope(reject))
        self.assertEqual(result.facts['phase'],'cancelled')
        self.assertEqual(result.facts['response_kind'],'cancelled')
        self.assertNotIn('round2_message',result.facts)
        self.assertFalse(result.allowed_actions)
        self.assertEqual(self.writes(),[])
