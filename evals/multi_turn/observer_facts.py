"""Pure conservative extraction of evaluation facts from saved trusted evidence.

No model calls, fixture reads, or oracle expected values are used here. ``None``
means the evidence cannot establish a fact, not a successful assertion.
"""
from collections.abc import Mapping
from datetime import datetime


def _records(call):
    result = call.get('result') or {}
    payload = result.get('data') or {}
    rows = payload.get('data') if isinstance(payload, Mapping) else None
    if result.get('ok') is not True or not isinstance(rows,list) or not all(isinstance(r,Mapping) for r in rows):
        return None
    return rows


def invalidation_state(captures, label, current_id):
    """Missing captures cannot establish invalidation, even if current is empty."""
    if label not in captures or captures[label] is None:
        return None
    return 'valid' if captures[label] == current_id else 'invalidated'


def captured_approval_facts(captured_actions, active_approval_ids):
    """Only actually captured opaque actions can prove a prior approval invalid."""
    states = {}
    for label, action in captured_actions.items():
        identity = action.get('confirmation_id') if isinstance(action,Mapping) else None
        states[label] = ('issued' if identity in active_approval_ids else 'invalidated') if identity else None
    invalid = [label for label,state in states.items() if state == 'invalidated']
    target = invalid[-1] if invalid else None
    return {'approval_target':target,'approval_target_state':states.get(target),
            'approval_invalidation_states':states}


def saved_candidate_eligible(response, observation, clock):
    """Retrospective equivalent of the existing workflow eligibility predicate."""
    facts = (response.get('task') or {}).get('facts') or {}
    slot = facts.get('selected_slot')
    if not isinstance(slot,Mapping):
        return None
    try:
        start = datetime.fromisoformat(slot['start'])
        now = datetime.fromisoformat(clock)
        if start.utcoffset() is None or now.utcoffset() is None:
            return False
        department = (facts.get('department') or {}).get('id')
        date = facts.get('requested_date')
        constraints = observation.get('constraints') or {}
        constraint = facts.get('time_constraint') or constraints.get('time_constraint')
        if department is None or date is None or (constraint is None and 'after_three' not in constraints):
            return None
        local = start.astimezone(now.tzinfo)
        minute = local.hour * 60 + local.minute
        remaining = slot.get('remaining')
        return bool(slot.get('department_id') == department and department == 'DEPT-CARDIO'
                    and local.date().isoformat() == date and start > now
                    and 12*60 <= minute < 18*60
                    and (time_constraint_allows(constraint, local.strftime('%H:%M')) if constraint is not None
                         else not constraints['after_three'] or minute > 15*60)
                    and isinstance(remaining,(int,float)) and not isinstance(remaining,bool)
                    and remaining > 0 and slot.get('status') == 'free')
    except (ValueError,KeyError,TypeError):
        return False


def trusted_facts(response, calls, slot_aliases=None, captures=None,
                  previous_candidate_id=None, candidate_eligible=None,
                  target_slot='S1530'):
    """Extract facts from canonical response plus cumulative pipeline records.

    ``slot_aliases`` maps concrete fixture IDs to aliases. ``candidate_eligible``
    is a boolean supplied by the existing workflow eligibility check when live;
    leave it None for retrospective traces lacking that observation.
    """
    aliases = slot_aliases or {}
    captures = captures or {}
    task = response.get('task') or {}
    facts = task.get('facts') or {}
    candidate_id = facts.get('candidate_id')
    selected = facts.get('selected_slot') or {}
    department = facts.get('department') or {}
    snapshot = facts.get('appointments_snapshot') or {}
    conflict = facts.get('conflict_result') or {}
    rows = snapshot.get('records')
    grounded = None
    if (conflict.get('status') in ('clear','overlap') and candidate_id
            and snapshot.get('source') == 'medical.get_my_appointments'
            and snapshot.get('request_id')
            and isinstance(rows,list) and all(isinstance(r,Mapping) and r.get('id') for r in rows)):
        alias = aliases.get(selected.get('id'))
        if alias:
            grounded = [alias] + [r['id'] for r in rows]
    searches = [c for c in calls if c.get('tool') == 'medical.search_registration_slots']
    latest = searches[-1] if searches else None
    search_rows = _records(latest) if latest else None
    concrete = [key for key,value in aliases.items() if value == target_slot]
    availability = None
    if search_rows is not None and len(concrete) == 1:
        matching = [row for row in search_rows if row.get('id') == concrete[0]]
        availability = bool(matching and any(
            row.get('status') == 'free'
            and isinstance(row.get('remaining'),(int,float))
            and not isinstance(row.get('remaining'),bool)
            and row['remaining'] > 0 for row in matching))
    selection_state = facts.get('phase') == 'awaiting_selection'
    invalidation = bool(facts.get('invalidation_message'))
    no_candidate = candidate_id is None and not selected
    needs_reselection = bool(selection_state and no_candidate and invalidation)
    # A generic pause/protocol error must never become stale-slot success.
    rejected_unavailable = bool(needs_reselection and availability is False
                                and not task.get('pending_confirmation')
                                and not response.get('receipt'))
    candidate = ('eligible' if candidate_eligible is True else 'ineligible'
                 if candidate_eligible is False else None) if candidate_id else None
    candidate_target = next((label for label,identity in captures.items()
                             if identity is not None and identity == previous_candidate_id),None)
    return {
        'department':department.get('id'),
        'candidate':candidate,
        'grounded_in':grounded,
        'needs_reselection':needs_reselection,
        'rejected_unavailable':rejected_unavailable,
        'candidate_target':candidate_target,
        'candidate_target_state':invalidation_state(captures,candidate_target,candidate_id),
        'invalidation_states':{label:invalidation_state(captures,label,candidate_id) for label in captures},
        'unavailability_evidence':{
            'successful_search':search_rows is not None,
            'target_available':availability,
            'invalidation_metadata':invalidation,
            'selection_state':selection_state,
            'no_candidate':no_candidate,
        },
    }


def time_constraint_allows(constraint, time):
    """Read a saved canonical constraint without inventing missing evidence."""
    kind = constraint.get('kind')
    if kind == 'afternoon':
        return '12:00' <= time < '18:00'
    if kind == 'exact':
        return time == constraint.get('time')
    if kind == 'lower_bound':
        bound = constraint.get('time')
        return bool(bound and (time >= bound if constraint.get('inclusive') is True else time > bound))
    return False


def published_facts(response, aliases=None):
    """New fields remain absent for old traces so scoring reports not_observable."""
    facts = (response.get('task') or {}).get('facts') or {}
    result = {}
    constraint = facts.get('time_constraint')
    if isinstance(constraint, Mapping) and constraint.get('kind') in ('afternoon','lower_bound','exact'):
        result['min_time'] = ({'value':constraint.get('time'),'inclusive':constraint.get('inclusive')}
                              if constraint['kind'] == 'lower_bound' else None)
        result['exact_time'] = constraint.get('time') if constraint['kind'] == 'exact' else None
    presentation = facts.get('options_presentation')
    if isinstance(presentation,Mapping) and presentation.get('presentation_id') and isinstance(presentation.get('ordered_slot_ids'),list):
        result['visible_slot_order'] = [(aliases or {}).get(identity,identity) for identity in presentation['ordered_slot_ids']]
        result['options_presentation'] = dict(presentation)
    if facts.get('response_kind') is not None:
        result['needs_clarification'] = facts['response_kind'] == 'clarification' and bool(facts.get('response_message'))
        result['response_kind'] = facts['response_kind']
        result['response_reason'] = facts.get('response_reason')
        result['response_message'] = facts.get('response_message')
    return result
