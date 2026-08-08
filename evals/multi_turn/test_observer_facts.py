"""Tests protect trusted-observer facts from optimistic inference."""
from copy import deepcopy
import unittest
from evals.multi_turn.observer_facts import trusted_facts, invalidation_state, captured_approval_facts, saved_candidate_eligible, published_facts


class ObserverFactsTests(unittest.TestCase):
    def setUp(self):
        self.aliases = {'slot-1530':'S1530','slot-1400':'S1400'}
        self.response = {'task':{'facts':{'phase':'awaiting_selection',
            'invalidation_message':'server invalidated candidate',
            'department':{'id':'DEPT-ACTUAL'}}},'receipt':None}
        self.calls = [{'tool':'medical.search_registration_slots','result':{
            'ok':True,'data':{'data':[{'id':'slot-1400','remaining':1,'status':'free'}]}}}]

    def extract(self,response=None,calls=None,**kw):
        return trusted_facts(response or self.response,self.calls if calls is None else calls,
                             self.aliases,**kw)

    def test_stale_slot_needs_successful_search_and_server_invalidation(self):
        result = self.extract()
        self.assertTrue(result['rejected_unavailable'])
        self.assertTrue(result['needs_reselection'])
        self.assertEqual(result['department'],'DEPT-ACTUAL')

    def test_all_refusal_or_missing_candidate_cannot_complete_stale_case(self):
        response = {'task':{'facts':{'phase':'awaiting_selection'}},'receipt':None}
        self.assertFalse(self.extract(response)['rejected_unavailable'])
        self.assertFalse(self.extract(response)['needs_reselection'])

    def test_failed_latest_search_does_not_reuse_older_success(self):
        calls = self.calls + [{'tool':'medical.search_registration_slots','result':{'ok':False}}]
        self.assertFalse(self.extract(calls=calls)['rejected_unavailable'])

    def test_available_slot_is_not_rejected_unavailable(self):
        calls = deepcopy(self.calls)
        calls[0]['result']['data']['data'].append({'id':'slot-1530','remaining':1,'status':'free'})
        self.assertFalse(self.extract(calls=calls)['rejected_unavailable'])

    def test_busy_slot_with_capacity_zero_is_unavailable(self):
        calls = deepcopy(self.calls)
        calls[0]['result']['data']['data'].append({'id':'slot-1530','remaining':0,'status':'busy'})
        self.assertTrue(self.extract(calls=calls)['rejected_unavailable'])

    def test_no_search_or_alias_is_unknown_unavailability(self):
        self.assertFalse(self.extract(calls=[])['rejected_unavailable'])
        self.assertIsNone(self.extract(calls=[])['unavailability_evidence']['target_available'])
        self.assertFalse(trusted_facts(self.response,self.calls,{})['rejected_unavailable'])

    def test_wrong_phase_or_remaining_candidate_blocks_reselection(self):
        for change in ({'phase':'planning'},{'candidate_id':'P2'}, {'selected_slot':{'id':'slot-1530'}}):
            response = deepcopy(self.response)
            response['task']['facts'].update(change)
            self.assertFalse(self.extract(response)['rejected_unavailable'])

    def test_grounding_uses_only_query_snapshot_records(self):
        response = deepcopy(self.response)
        response['task']['facts'].update(candidate_id='P2',selected_slot={'id':'slot-1530'},
            conflict_result={'status':'clear'},appointments_snapshot={
                'source':'medical.get_my_appointments','request_id':'query-1',
                'records':[{'id':'APT-OBSERVED'}]})
        result = self.extract(response,candidate_eligible=True)
        self.assertEqual(result['grounded_in'],['S1530','APT-OBSERVED'])
        self.assertEqual(result['candidate'],'eligible')
        self.assertIsNone(self.extract(response)['candidate'])
        response['task']['facts']['appointments_snapshot']['records'] = None
        self.assertIsNone(self.extract(response)['grounded_in'])

    def test_missing_capture_never_proves_invalidation(self):
        self.assertIsNone(invalidation_state({},'P2',None))
        self.assertIsNone(invalidation_state({'P2':None},'P2','P1'))
        self.assertEqual(invalidation_state({'P2':'candidate-id'},'P2',None),'invalidated')
        result = self.extract(captures={'P2':'candidate-id'},previous_candidate_id='candidate-id')
        self.assertEqual(result['candidate_target'],'P2')
        self.assertEqual(result['candidate_target_state'],'invalidated')

    def test_approval_target_requires_real_captured_action(self):
        facts = captured_approval_facts({'OLD':{'confirmation_id':'opaque-1'},'MISSING':None},[])
        self.assertEqual(facts['approval_target'],'OLD')
        self.assertEqual(facts['approval_target_state'],'invalidated')
        self.assertIsNone(facts['approval_invalidation_states']['MISSING'])
        self.assertIsNone(captured_approval_facts({},[])['approval_target'])
        self.assertEqual(captured_approval_facts({'A':{'confirmation_id':'opaque-1'}},['opaque-1'])['approval_invalidation_states']['A'],'issued')

    def test_saved_eligibility_checks_actual_department_and_boundary(self):
        response = {'task':{'facts':{'department':{'id':'DEPT-CARDIO'},'requested_date':'2026-10-20',
            'selected_slot':{'department_id':'DEPT-CARDIO','start':'2026-10-20T15:00:00+08:00',
                             'remaining':1,'status':'free'}}}}
        self.assertFalse(saved_candidate_eligible(response,{'constraints':{'after_three':True}},'2026-10-13T09:00:00+08:00'))
        self.assertTrue(saved_candidate_eligible(response,{'constraints':{'after_three':False}},'2026-10-13T09:00:00+08:00'))
        response['task']['facts']['selected_slot']['remaining'] = True
        self.assertFalse(saved_candidate_eligible(response,{'constraints':{'after_three':False}},'2026-10-13T09:00:00+08:00'))

    def test_new_fields_require_published_evidence(self):
        self.assertEqual(published_facts({'task':{'facts':{}}}),{})
        response = {'task':{'facts':{'time_constraint':{'kind':'lower_bound','time':'15:00','inclusive':True},
            'options_presentation':{'presentation_id':'view-1','revision':2,'ordered_slot_ids':['slot-1400','slot-1530'],
                                    'visible_times':['14:00','15:30'],'source_request_id':'search-1'},
            'response_kind':'clarification','response_reason':'ambiguous','response_message':'請問查甚麼？'}}}
        result = published_facts(response,self.aliases)
        self.assertEqual(result['visible_slot_order'],['S1400','S1530'])
        self.assertTrue(result['needs_clarification'])
        self.assertEqual(result['min_time'],{'value':'15:00','inclusive':True})
        self.assertIsNone(result['exact_time'])
        response['task']['facts']['time_constraint'] = {'kind':'exact','time':'14:00'}
        result = published_facts(response)
        self.assertEqual(result['exact_time'],'14:00')
        self.assertIsNone(result['min_time'])

    def test_saved_canonical_constraints_override_legacy_boolean(self):
        response = {'task':{'facts':{'department':{'id':'DEPT-CARDIO'},'requested_date':'2026-10-20',
            'time_constraint':{'kind':'lower_bound','time':'15:00','inclusive':True},
            'selected_slot':{'department_id':'DEPT-CARDIO','start':'2026-10-20T15:00:00+08:00',
                             'remaining':1,'status':'free'}}}}
        self.assertTrue(saved_candidate_eligible(response,{'constraints':{'after_three':True}},'2026-10-13T09:00:00+08:00'))
        response['task']['facts']['time_constraint'] = {'kind':'exact','time':'14:00'}
        self.assertFalse(saved_candidate_eligible(response,{},'2026-10-13T09:00:00+08:00'))


if __name__ == '__main__':
    unittest.main()
