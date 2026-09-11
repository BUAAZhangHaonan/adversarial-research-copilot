"""Current lightweight idea understanding, derived without a summarizer call."""
from __future__ import annotations

from copy import deepcopy
import json


EVIDENCE_LIMITED_LABEL = '文献受限，保留待查'


def evidence_limit_summaries(state, task_prefix=None):
    """Expose unresolved questions, not full requests or retry metadata."""
    summaries = []
    for key, entry in (state.get('evidence_limits') or {}).items():
        if task_prefix and key != task_prefix and not key.startswith(task_prefix + '.'):
            continue
        questions = []
        for request in entry.get('unresolved_evidence_requests', []):
            question = request if isinstance(request, str) else request.get('question') or request.get('blocked_question')
            if question and question not in questions:
                questions.append(question)
        summaries.append({'task': key, 'reason': entry.get('reason', ''),
                          'status': entry.get('status', ''), 'unresolved_questions': questions})
    return summaries


def current_idea_view(record):
    """Project current accepted understanding; full originals remain in read_record."""
    seed = record.get('seed') or {}
    triage = record.get('triage') or {}
    limited = record.get('status') == 'evidence_limited'
    note = {} if limited else record.get('note') or {}
    if note:
        current = note.get('current_understanding')
        if current is not None:
            understanding = deepcopy(current)
            origin = 'explicit_note'
        else:
            # Historical notes did not expose a separate corrected view. Use
            # their actual final reasoning, never revive the original premise.
            understanding = {
                'core_insight': note.get('reason', ''),
                'invalidated_premises': deepcopy(note.get('changes_from_seed', [])),
                'decisive_unknown': note.get('next_question', ''),
                'why_existing_insufficient': note.get('main_risk', ''),
            }
            origin = 'historical_note'
        decision = note.get('decision')
        title = (note.get('seed') or {}).get('title') or seed.get('title', '')
    else:
        understanding = {
            'core_insight': seed.get('insight', ''),
            'invalidated_premises': [],
            'decisive_unknown': seed.get('key_unknown', ''),
            'why_existing_insufficient': triage.get('reason') or seed.get('difference_from_known', ''),
        }
        origin = 'evidence_limited_seed' if limited else 'pending_seed'
        decision = 'evidence_limited' if limited else triage.get('action') or record.get('status', 'pending')
        if limited:
            understanding['why_existing_insufficient'] = '文献核查受限，尚不能确认已有工作是否覆盖该想法。'
        title = seed.get('title', '')
    view = {key: record.get(key) for key in ('idea_id', 'run_id', 'draw_id')}
    view.update(title=title, status=record.get('status', 'pending'), decision=decision,
                current_understanding=understanding, origin=origin)
    if triage.get('candidate_relation') is not None:
        view['candidate_relation'] = deepcopy(triage['candidate_relation'])
    return view


def discovery_idea_index_text(record):
    """Search the latest projection and original question, without changing either."""
    return ' '.join([record.get('topic', ''), (record.get('seed') or {}).get('question', ''),
                     json.dumps(current_idea_view(record), ensure_ascii=False),
                     json.dumps([] if record.get('status') == 'evidence_limited' else
                                (record.get('note') or {}).get('changes_from_seed', []), ensure_ascii=False)])
