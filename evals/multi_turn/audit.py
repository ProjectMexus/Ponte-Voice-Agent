"""Re-score retained first-attempt evidence after observer corrections.

No HTTP, model requests, backend writes, or changes to original files.
Run: python -m evals.multi_turn.audit <existing-run-directory>
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from .observer_facts import trusted_facts
from .runner import SPEC, save, report
from .scoring import score_case, score_track


def audit(directory):
    original = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    destination = directory / 'observer-audit-v2'
    destination.mkdir(exist_ok=False)
    results, changes = [], []
    for old_score in original['results']:
        track, case_id = old_score['track'], old_score['case_id']
        case = next(c for c in spec['cases'] if c['id'] == case_id)
        source = directory / track / case_id
        evidence = json.loads((source / 'evidence.json').read_text(encoding='utf-8'))
        rows = [json.loads(line) for line in (source / 'trace.jsonl').read_text(encoding='utf-8').splitlines()]
        observations, captures, actions, previous = [], {}, {}, {}
        last_proof = {}
        for row in rows:
            if 'event' not in row or 'control' in row['event']:
                continue
            observation = deepcopy(row['observation'])
            raw = row['response']
            snapshot = row['snapshot']
            aliases = {s['id']: alias for alias, s in snapshot['fixture']['slots'].items()}
            facts = (raw.get('task') or {}).get('facts', {})
            slot = facts.get('selected_slot') or {}
            constraints = observation.get('constraints') or {}
            # Validate only the existing demo's representable constraints. Never
            # manufacture inclusive/exact-time support from the case oracle.
            eligible = bool(slot.get('id') in aliases and slot.get('status') == 'free'
                            and slot.get('remaining', 0) > 0
                            and slot.get('department_id') == (facts.get('department') or {}).get('id')
                            and slot.get('start', '')[:10] == facts.get('requested_date')
                            and (not constraints.get('after_three') or slot.get('start', '')[11:16] > '15:00'))
            proof = trusted_facts(raw, snapshot['calls'], aliases, captures,
                                  previous.get('candidate_id'), eligible if slot else None)
            for field in ('department', 'candidate', 'grounded_in', 'needs_reselection'):
                observation[field] = proof[field]
            if row['event'].get('expect', {}).get('candidate_target'):
                target = row['event']['expect']['candidate_target']
                observation['candidate_target_state'] = proof['invalidation_states'].get(target)
                observation['candidate_target'] = proof['candidate_target']
            current_actions = [(a.get('event') or {}).get('confirmation_id') for a in raw.get('workspace', {}).get('actions', [])]
            invalidated = [label for label, action in actions.items() if action.get('confirmation_id') not in current_actions]
            if invalidated:
                observation['approval_target'] = invalidated[-1]
                observation['approval_target_state'] = 'invalidated'
            for kind, label in row['event'].get('capture', {}).items():
                if kind == 'candidate':
                    captures[label] = observation.get('candidate_id')
                if kind == 'approval':
                    action = next((a['event'] for a in raw.get('workspace', {}).get('actions', []) if (a.get('event') or {}).get('decision') == 'approve'), None)
                    if action:
                        actions[label] = action
            differences = {key: {'before': row['observation'].get(key), 'after': value}
                           for key, value in observation.items() if row['observation'].get(key) != value}
            if differences:
                changes.append({'track': track, 'case_id': case_id, 'step': row['step'], 'changes': differences})
            observations.append(observation)
            previous, last_proof = observation, proof
        final = deepcopy(evidence.get('final', {}))
        if last_proof:
            final['needs_reselection'] = last_proof['needs_reselection']
            final['rejected_unavailable'] = last_proof['rejected_unavailable']
        score = score_case(case, observations, evidence.get('dispatches'), evidence.get('backend_effects'), evidence.get('coverage'), final, evidence.get('error'))
        score['track'] = track
        results.append(score)
    aggregate = {track: score_track([r for r in results if r['track'] == track]) for track in ('scripted', 'real_model')}
    save(destination / 'results.json', {'metadata': original['metadata'], 'results': results, 'aggregate': aggregate})
    save(destination / 'changes.json', changes)
    (destination / 'report.md').write_text(report(results, original['metadata']), encoding='utf-8')
    print(json.dumps(aggregate, indent=2))
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    audit(parser.parse_args().directory)
