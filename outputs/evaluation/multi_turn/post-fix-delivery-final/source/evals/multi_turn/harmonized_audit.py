"""Conservative, separate re-audit of legacy evidence; never overwrite a pilot."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from .observer_facts import published_facts, saved_candidate_eligible, trusted_facts
from .runner import SPEC, save, report
from .scoring import score_case, score_track


def audit(source, destination):
    original = json.loads((source / 'results.json').read_text(encoding='utf-8'))
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    destination.mkdir(parents=True, exist_ok=False)
    results, changes = [], []
    for old in original['results']:
        case = next(c for c in spec['cases'] if c['id'] == old['case_id'])
        directory = source / old['track'] / old['case_id']
        evidence = json.loads((directory / 'evidence.json').read_text(encoding='utf-8'))
        observations, captures, previous, last_proof = [], {}, {}, {}
        for line in (directory / 'trace.jsonl').read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if 'event' not in row or 'control' in row['event']: continue
            observation = deepcopy(row['observation'])
            response, snapshot = row['response'], row['snapshot']
            aliases = {s['id']: alias for alias,s in snapshot['fixture']['slots'].items()}
            proof = trusted_facts(response, snapshot['calls'], aliases, captures,
                previous.get('candidate_id'), saved_candidate_eligible(response, observation, spec['clock']))
            for field in ('department','candidate','grounded_in','needs_reselection','rejected_unavailable'):
                observation[field] = proof[field]
            facts = (response.get('task') or {}).get('facts') or {}
            # Legacy exact_time was hardcoded None. No saved typed constraint can
            # prove it; missing snapshot/clarification metadata stays missing.
            if 'time_constraint' not in facts:
                observation.pop('exact_time', None)
            for field in ('visible_slot_order','needs_clarification'):
                observation.pop(field, None)
            observation.update(published_facts(response, aliases))
            if 'approval_registry' not in observation:
                for field in ('approval_target','approval_target_state','approval_invalidation_states'):
                    observation.pop(field,None)
            for kind,label in row['event'].get('capture',{}).items():
                if kind == 'candidate': captures[label] = observation.get('candidate_id')
            differences = {key:{'before':row['observation'].get(key),'after':observation.get(key),'removed':key not in observation}
                for key in set(row['observation']) | set(observation)
                if row['observation'].get(key) != observation.get(key) or (key in row['observation']) != (key in observation)}
            if differences: changes.append({'track':old['track'],'case_id':old['case_id'],'step':row['step'],'changes':differences})
            observations.append(observation)
            previous, last_proof = observation, proof
        final = deepcopy(evidence.get('final',{}))
        for field in ('needs_reselection','rejected_unavailable'):
            if last_proof: final[field] = last_proof[field]
        score = score_case(case, observations, evidence.get('dispatches'), evidence.get('backend_effects'), evidence.get('coverage'), final, evidence.get('error'))
        score['track'] = old['track']
        results.append(score)
    aggregate = {track:score_track([r for r in results if r['track']==track]) for track in ('scripted','real_model')}
    save(destination/'results.json',{'metadata':original['metadata'],'results':results,'aggregate':aggregate,
        'provenance':{'source':str(source),'method':'Conservative legacy evidence only; missing canonical exact/options/clarification/approval registry remains not_observable. Original pilot scores and files untouched.'}})
    save(destination/'changes.json',changes)
    (destination/'report.md').write_text(report(results,original['metadata']),encoding='utf-8')
    print(json.dumps(aggregate,indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args = parser.parse_args()
    audit(args.source,args.destination)
