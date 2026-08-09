"""Evaluation-only observer over the existing HTTP/MCP acceptance harness.

Each adapter owns temporary backend files. Fixture function patching is process
local: run cases in separate processes (as the runner does).
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
import os
import shutil
import threading
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from tests import test_demo_agent_e2e as h
from middleware.config import load_dotenv
from middleware.demo_time import parse_time_constraint, selection_target
from middleware.demo_model import RegistryToolNameClient
from middleware.llm_transport import OpenAICompatibleChatClient
from mock_backends.core.persistence import JsonLinesTextRepository
from mock_backends.medical.fixtures import cardiology_demo_slots
from .observer_facts import trusted_facts, captured_approval_facts, published_facts


class Adapter:
    def __init__(self, case, spec, track, run_directory=None):
        self.case, self.spec, self.track = case, spec, track
        self.h = h.DemoAgentEndToEndTests()
        self.captures = {}
        self.actions = {}
        self.observations = []
        self.dispatches = []
        self.calls = []
        self.model_exchanges = []
        self.current_event = None
        self.intervention_ids = set()
        self.last = {}
        self.previous = {}
        self.step_number = 0
        self.booking_before = 0
        self.write_before = 0
        self.initial_candidate = None
        self.run_directory = Path(run_directory) if run_directory else None
        self.metadata = {'model': 'queued-native-decisions', 'temperature': 0, 'prompt_config': 'DemoMedicalWorkflow.SYSTEM_PROMPT/runtime-control', 'fixture_version': 1}

    def __enter__(self):
        templates = cardiology_demo_slots(datetime.fromisoformat(self.spec['clock']).date())
        template = next(s for s in templates if s['start'][11:16] == '14:00')
        aliases = self.spec['fixture_contract']['profiles'][self.case['fixture']]['slot_aliases']
        self.slots = {}
        for alias in aliases:
            slot = deepcopy(template)
            slot.update(self.spec['fixture_contract']['slots'][alias])
            slot['id'] = 'SLOT-EVAL-' + self.case['id'] + '-' + alias
            slot['remaining'] = 1
            slot['status'] = 'free'
            self.slots[alias] = slot
        self.reverse = {s['id']: a for a,s in self.slots.items()}
        self.fixture_patch = patch('mock_backends.medical.service.registration_slots', lambda *_: deepcopy(list(self.slots.values())))
        self.fixture_patch.start()
        try:
            temp_root = Path('outputs/evaluation/multi_turn/.temporary').resolve()
            temp_root.mkdir(parents=True, exist_ok=True)
            with patch('tempfile.tempdir', str(temp_root)):
                self.h.setUp()
            def http_json(method, url, body=None, headers=None):
                request = Request(url, method=method,
                    data=None if body is None else json.dumps(body,ensure_ascii=False).encode('utf-8'),
                    headers={'Content-Type':'application/json', **(headers or {})})
                try:
                    with build_opener(ProxyHandler({})).open(request,timeout=120 if self.track != 'scripted' else 15) as result:
                        return result.status, json.loads(result.read())
                except HTTPError as error:
                    try:
                        return error.code, json.loads(error.read())
                    finally:
                        error.close()
            self.h.http_json = http_json
            self.h.session_id = 'EVAL-' + self.case['id'] + '-' + self.track
            if self.spec['fixture_contract']['profiles'][self.case['fixture']]['appointments']:
                appointment = deepcopy(self.spec['fixture_contract']['existing_appointment'])
                appointment.update(patient_id=h.PATIENT, patient={'id': h.PATIENT}, department={'id':'DEPT-OTHER','name':'既有預約'})
                JsonLinesTextRepository(self.h.data_dir / 'medical' / 'appointments.txt').insert(appointment)
            if self.track in ('real', 'real_model'):
                load_dotenv()
                url = os.environ.get('PONTE_DEMO_LLM_API_URL') or os.environ.get('PONTE_LLM_API_URL')
                if not url:
                    raise RuntimeError('infrastructure: configured real-model endpoint missing (PONTE_DEMO_LLM_API_URL/PONTE_LLM_API_URL)')
                model = os.environ.get('PONTE_DEMO_LLM_MODEL') or os.environ.get('PONTE_LLM_MODEL','gpt-4o-mini')
                client = OpenAICompatibleChatClient(url, api_key=os.environ.get('PONTE_DEMO_LLM_API_KEY') or os.environ.get('PONTE_LLM_API_KEY',''), model=model, timeout=30)
                self.h.app.demo_workflow.client = RegistryToolNameClient(client)
                self.h.app.demo_workflow.model_mode = 'real'
                self.h.app.demo_agent_mode = 'real'
                self.metadata.update(model=model, endpoint_type='OpenAI-compatible chat completions')
            client = self.h.app.demo_workflow.client
            original_complete = client.complete
            def complete(messages, **options):
                exchange = {'messages':deepcopy(messages), 'options':deepcopy(options)}
                self.model_exchanges.append(exchange)
                try:
                    response = original_complete(messages, **options)
                    exchange['response'] = deepcopy(response)
                    return response
                except Exception as exc:
                    exchange['error_type'] = type(exc).__name__
                    cause = exc
                    while cause.__cause__ is not None:
                        cause = cause.__cause__
                    exchange['root_error_type'] = type(cause).__name__
                    if isinstance(cause, HTTPError):
                        exchange['http_status'] = cause.code
                    raise
            client.complete = complete
            self.metadata['dataset_hash'] = hashlib.sha256(json.dumps({'slots':self.slots,'appointments':self.h.appointments()},sort_keys=True).encode()).hexdigest()
            original = self.h.app.pipeline.dispatch
            def observe(call):
                record = {'id': str(len(self.calls)+1), 'tool': call.name, 'call_id':call.step_id, 'input':deepcopy(call.arguments.get('input',{}))}
                self.calls.append(record)
                if call.name == 'medical.create_registration':
                    state = self.state()
                    proposal = state.proposals.get(state.pending_id) if state else None
                    event = self.current_event or {}
                    expected = {'type':'confirmation_decision','task_id':proposal.task_id,
                                'confirmation_id':proposal.frozen.proposal_id,
                                'candidate_id':state.task['facts'].get('candidate_id'),
                                'decision':'approve','action_id':dict(proposal.actions).get('approve')} if proposal else None
                    authorized = bool(proposal and state.proposal_status.get(state.pending_id) == 'submitting'
                                      and event == expected and expected['action_id'])
                    binding = bool(proposal and state.candidate
                                   and proposal.frozen.tool_arguments() == state.candidate.frozen.tool_arguments()
                                   and proposal.revision == state.revision
                                   and proposal.task_id == state.task['task_id']
                                   and proposal.session_id == state.session_id
                                   and proposal.frozen.verify_integrity()
                                   and not proposal.frozen.is_expired(self.h.clock.now().timestamp())
                                   and self.h.app.demo_workflow._eligible_slot(state,proposal.frozen.tool_arguments()['slot'])
                                   and proposal.frozen.tool_arguments()['input'] == call.arguments.get('input')) if proposal else False
                    record.update(approval_id=state.pending_id if state else None, authorized=authorized, binding_valid=binding, labels=[], idempotency_key=call.arguments.get('context',{}).get('idempotency_key'))
                    self.dispatches.append(record)
                result = original(call)
                record['result'] = result.to_dict()
                return result
            self.h.app.pipeline.dispatch = observe
            return self
        except BaseException:
            self.__exit__(None,None,None)
            raise

    def __exit__(self, *args):
        if self.run_directory and hasattr(self.h,'data_dir'):
            self.run_directory.mkdir(parents=True,exist_ok=True)
            shutil.copytree(self.h.data_dir,self.run_directory / 'backend_data',dirs_exist_ok=True)
        self.h.doCleanups()
        self.fixture_patch.stop()

    def state(self):
        states = self.h.app.demo_workflow._states
        return next(iter(states.values()),None)

    def queue(self, text):
        # A previous protocol refusal may leave unused planned responses. They
        # belong to that turn, never to the next user's meaning.
        with self.h.model.lock:
            self.h.model.responses.clear()
        n = self.step_number
        def search(): return h.search_call('eval-search-'+str(n))
        def proposal(alias):
            slot = self.slots[alias]
            return h.native_call('eval-proposal-'+str(n),'medical.create_registration',{'patient_id':h.PATIENT,'department_id':'DEPT-CARDIO','doctor_id':slot['doctor_id'],'slot_id':slot['id'],'consent':True})
        state = self.state()
        if not state:
            self.h.model.add(h.native_call('eval-depts','medical.list_departments',{'keyword':'Cardiology','active_only':True}),search(),proposal(next(iter(self.slots))))
            return
        constraint = parse_time_constraint(text)
        target = selection_target(text,state.task.get('facts',{}).get('options_presentation'))
        if constraint is not None and constraint != state.task.get('facts',{}).get('time_constraint'):
            from middleware.demo_time import matches_time
            eligible = sorted((s for s in self.slots.values() if matches_time(constraint,s['start'][11:16])),key=lambda s:s['start'])
            decisions = [h.control('update_constraints',time_constraint=constraint),search()]
            if eligible:
                decisions.append(proposal(self.reverse[eligible[0]['id']]))
            self.h.model.add(*decisions)
        elif '撞' in text:
            self.h.model.add(h.control('answer_question'))
        elif '之前' in text:
            self.h.model.add(h.control('query_appointments'))
        elif target and state.candidate:
            self.h.model.add(h.control('select_slot',target=target))
        elif target:
            self.h.model.add(h.control('clarify',message='所選時段已失效，請重新選擇。'))
        elif '返去' in text:
            self.h.model.add(h.control('resume_booking'))
        else:
            self.h.model.add(h.control('clarify',message='請說明查詢內容，或選定時段並點正式確認卡。'))

    def event(self, step):
        self.step_number += 1
        if 'control' in step:
            slot = self.slots[step['slot']]
            status, response = self.h.http_json('POST',f'http://127.0.0.1:{self.h.backend.server_port}/mock/medical/v1/registrations',{'patient_id':'PAT-OTHER','department_id':'DEPT-CARDIO','doctor_id':slot['doctor_id'],'slot_id':slot['id'],'consent':True},{'Authorization':'Bearer mock-user-token','X-Patient-Id':'PAT-OTHER','Idempotency-Key':'FIXTURE-OCCUPY'})
            if status != 201: raise RuntimeError('fixture intervention failed: '+str(status))
            self.intervention_ids.add(response['data']['id'])
            return {'observation': {'agent_write_delta':0}, 'response':response, 'http_status':status}
        call_start = len(self.calls)
        if 'user' in step:
            self.current_event = {'type':'user_utterance','task_id':None,'content':step['user']}
            if self.track == 'scripted': self.queue(step['user'])
            response = self.h.say(step['user'])
        else:
            target = step['target']
            if target not in self.actions:
                raise RuntimeError('server issued no approval action for '+target)
            event = deepcopy(self.actions[target])
            self.current_event = event
            if step['action'] == 'approve_concurrently':
                barrier = threading.Barrier(step.get('copies',2))
                def send(_):
                    barrier.wait(timeout=5)
                    return self.h.interact(event,allow_rejection=True)
                with ThreadPoolExecutor(max_workers=step.get('copies',2)) as pool:
                    responses = list(pool.map(send,range(step.get('copies',2))))
                response = next((r for r in responses if r.get('receipt')),responses[0])
                response = deepcopy(response)
                response['evaluation_concurrent_responses'] = responses
            else: response = self.h.interact(event,allow_rejection=True)
        self.last = response
        observation = self.normalize(response, self.calls[call_start:])
        for kind,label in step.get('capture',{}).items():
            if kind == 'candidate': self.captures[label] = observation.get('candidate_id')
            elif kind == 'approval':
                actions = response.get('workspace',{}).get('actions',[])
                action = next((a['event'] for a in actions if a.get('event',{}).get('decision')=='approve'),None)
                if action: self.actions[label] = deepcopy(action)
        observation['revalidated_candidate'] = next((label for label,value in self.captures.items() if value == observation.get('candidate_id')),None)
        if observation.get('candidate_id') != self.previous.get('candidate_id'):
            observation['candidate_target'] = next((label for label,value in self.captures.items() if value == self.previous.get('candidate_id')),None)
        observation.update(captured_approval_facts(self.actions,self.active_approvals()))
        self.observations.append(observation)
        self.previous = deepcopy(observation)
        return {'observation':observation,'response':response,'http_status':200}

    def active_approvals(self):
        state = self.state()
        if not state or state.phase != 'awaiting_approval' or not state.pending_id:
            return []
        proposal = state.proposals.get(state.pending_id)
        return [state.pending_id] if (proposal and state.candidate
            and state.proposal_status.get(state.pending_id) == 'pending'
            and proposal.revision == state.revision
            and proposal.frozen.verify_integrity()
            and not proposal.frozen.is_expired(self.h.clock.now().timestamp())
            and proposal.frozen.tool_arguments() == state.candidate.frozen.tool_arguments()) else []

    def normalize(self, response, calls):
        state = self.state()
        task = state.task if state else response.get('task',{})
        facts = task.get('facts',{})
        candidate = state.candidate if state else None
        slot = candidate.frozen.tool_arguments()['slot'] if candidate else {}
        records = [r for r in self.h.appointments() if r.get('patient_id') == h.PATIENT and r.get('id')!='APT-EXIST-1']
        constraints = {'department':(facts.get('department') or {}).get('id'),'date':state.date,'time_constraint':deepcopy(facts.get('time_constraint'))} if state else None
        current = {'task_id':task.get('task_id'),'candidate_id':facts.get('candidate_id'),'constraints':constraints}
        observation = dict(current, department=constraints.get('department') if constraints else None,date=state.date if state else None, candidate='eligible' if candidate else None,candidate_slot=self.reverse.get(slot.get('id')),approval='issued' if self.active_approvals() else 'none',approval_consumed=bool(records),eligible_slot_set=sorted(a for a,s in self.slots.items() if (state is not None and self.h.app.demo_workflow._eligible_slot(state,s))), tools_called=[c['tool'] for c in calls],write_delta=len(self.dispatches)-self.write_before,booking_delta=len(records)-self.booking_before,conflict=facts.get('conflict_result',{}).get('status'),grounded_in=[], receipt_slot=self.reverse.get(records[-1].get('slot_id')) if response.get('receipt') and records else None, receipt_verified=bool(response.get('receipt') and records), reported_booked=bool(response.get('receipt')), needs_reselection=bool(state and not candidate and state.phase!='completed'), approval_for_slot_S1530=bool(self.active_approvals() and self.reverse.get(slot.get('id'))=='S1530'),rejected=bool(response.get('error') or response.get('recovery') or response.get('task',{}).get('status')!='completed'),one_idempotency_key=len({d.get('idempotency_key') for d in self.dispatches})==1,already_processed_or_same_receipt=bool(response.get('receipt') and self.previous.get('receipt_verified')))
        observation['tool_called'] = observation['tools_called']
        observation['preserve'] = {k:self.previous.get(k)==v for k,v in current.items()}
        observation['old_candidate'] = 'invalidated' if self.previous.get('candidate_id') and self.previous.get('candidate_id') != current['candidate_id'] else 'valid'
        snapshot = facts.get('appointments_snapshot') or {}
        receipt = response.get('receipt') or {}
        verified = False
        if receipt and records:
            record = records[-1]
            for dispatch in self.dispatches:
                payload = dispatch.get('result',{}).get('data',{})
                backend = payload.get('data',{})
                reference = payload.get('receipt',{}).get('reference')
                verified = verified or bool(dispatch.get('authorized') and dispatch.get('binding_valid')
                    and receipt.get('receipt_id') == reference
                    and backend.get('id') == record.get('id')
                    and backend.get('status') == record.get('status') == 'booked'
                    and backend.get('slot_id') == record.get('slot_id') == dispatch.get('input',{}).get('slot_id')
                    and backend.get('patient_id') == record.get('patient_id') == h.PATIENT
                    and backend.get('start') == record.get('start')
                    and backend.get('end') == record.get('end'))
        observation['receipt_verified'] = verified
        observation['receipt_slot'] = self.reverse.get(records[-1].get('slot_id')) if verified else None
        observation['rejected'] = bool(response.get('error'))
        if observation['conflict'] == 'clear' and candidate and snapshot.get('source')=='medical.get_my_appointments':
            observation['grounded_in'] = [observation['candidate_slot']] + [r['id'] for r in self.h.appointments() if r.get('id')=='APT-EXIST-1']
        eligible = self.h.app.demo_workflow._eligible_slot(state,slot) if candidate else None
        audited = trusted_facts(response,self.calls,self.reverse,self.captures,
                                self.previous.get('candidate_id'),eligible)
        observation.update(audited)
        observation.update(published_facts(response,self.reverse))
        observation['approval_registry'] = dict(state.proposal_status) if state else {}
        observation['manual_review'] = [field for field in ('visible_slot_order','needs_clarification') if field not in observation]
        self.booking_before, self.write_before = len(records),len(self.dispatches)
        return observation

    def snapshot(self):
        records = [r for r in self.h.appointments() if r.get('id')!='APT-EXIST-1' and r.get('id') not in self.intervention_ids]
        effects = []
        for record in records:
            matching = next((d for d in self.dispatches
                             if (d.get('result',{}).get('data') or {}).get('data',{}).get('id') == record.get('id')),None)
            effects.append({'id':record['id'],'dispatch_id':matching['id'] if matching else None,'slot':self.reverse.get(record.get('slot_id'))})
        final = dict(self.previous)
        final.update(booking_count=len(records),write_count=len(self.dispatches),tools_called=[c['tool'] for c in self.calls],constraints_preserved=self.previous.get('constraints',{}).get('time_constraint') == {'kind':'lower_bound','time':'15:00','inclusive':False},rejected_unavailable=self.previous.get('rejected_unavailable',False))
        return {'dispatches':deepcopy(self.dispatches),'backend_effects':effects,'coverage':{'dispatch_trace':all('result' in d for d in self.dispatches),'backend_effects':True},'final':final,'metadata':self.metadata,'calls':deepcopy(self.calls),'model_exchanges':deepcopy(self.model_exchanges),'fixture':{'slots':deepcopy(self.slots),'appointments':deepcopy(self.h.appointments()),'intervention_ids':sorted(self.intervention_ids)}}
