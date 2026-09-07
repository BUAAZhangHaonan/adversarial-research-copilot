"""Explicit revisions of failed frozen-comparison tasks, preserving prior results."""
from __future__ import annotations

import json
from pydantic import ValidationError

from .schemas import Envelope, RESULT_SCHEMAS, utc_now
from .store import StateError
from .validation import output_validation_errors


COMPARISON_TASKS = {
    'frame': ('discovery', 'FRAME'), 'family': ('discovery', 'NEXT_DRAW'),
    'compose': ('discovery', 'COMPOSE'), 'novelty': ('novelty_examiner', 'INVOKE'),
    'selection': ('selector', 'INVOKE'),
    'judge': ('evaluator', 'INVOKE'),
}


def prepare_comparison_retry(store, ledger, source_run_id, system, task_key, reason):
    """Record one user request; only execution creates the new physical task."""
    if system not in ('ARC', 'direct-Pro', 'evaluator') or task_key not in COMPARISON_TASKS or not reason.strip():
        raise StateError('COMPARISON_RETRY_INVALID_SYSTEM_TASK_OR_REASON')
    if ((system == 'evaluator') != (task_key == 'judge')
            or (system == 'direct-Pro' and task_key in ('frame', 'family'))):
        raise StateError('COMPARISON_RETRY_TASK_NOT_IN_SYSTEM')
    run_id = source_run_id + '.comparison.' + system
    run = store.get_run(run_id)
    if run.mode != 'evaluation' or run.status not in ('PAUSED_PROTOCOL', 'PAUSED_EXTERNAL'):
        raise StateError('COMPARISON_RETRY_REQUIRES_FAILED_OR_BLOCKED_RUN')
    if any(c['state'] not in ('SETTLED', 'NOT_SENT') for c in ledger.list_calls(run.budget_account_id)):
        raise StateError('COMPARISON_RETRY_HAS_UNSETTLED_CALLS')
    frozen_path = f'evaluations/{source_run_id}/evidence.json'
    store.read_artifact(frozen_path)
    retries = dict(run.state.get('comparison_task_retries', {}))
    history = list(retries.get(task_key, []))
    previous_key = history[-1]['replacement_key'] if history else task_key
    source = store.get_task(f'{run_id}.{previous_key}')
    if (source is None or source.status not in ('PAUSED_PROTOCOL', 'PAUSED_EXTERNAL')
            or source.accepted_result is not None or not source.response_artifact_path
            or not source.rendered_prompt_path):
        raise StateError('COMPARISON_RETRY_REQUIRES_UNACCEPTED_FAILED_TASK')
    envelopes = dict(run.state.get('comparison_envelopes', {}))
    cached = envelopes.get(task_key)
    if cached is not None and cached.get('result_status') == 'complete':
        raise StateError('COMPARISON_RETRY_CANNOT_REPLACE_COMPLETED_RESULT')
    role, task = COMPARISON_TASKS[task_key]
    snapshot = json.loads(store.read_artifact(source.rendered_prompt_path))
    if snapshot['prompt_id'] != f'{role}.{task}':
        raise StateError('COMPARISON_RETRY_PROMPT_ROLE_MISMATCH')
    saved = json.loads(store.read_artifact(source.response_artifact_path))
    subject = saved.get('subject')
    expected = {'campaign_id': run.campaign_id, 'run_id': run_id,
                'card_id': run.card_id, 'card_version': run.card_version}
    if subject != expected:
        raise StateError('COMPARISON_RETRY_SUBJECT_CHANGED')
    if saved.get('original_tools') or saved.get('tool_trace'):
        raise StateError('COMPARISON_RETRY_REQUIRES_FROZEN_OFFLINE_TASK')
    raw = ((saved.get('response') or {}).get('message') or {}).get('content') or ''
    if source.status == 'PAUSED_EXTERNAL':
        try:
            blocked = json.loads(raw).get('result_status') == 'blocked'
        except (ValueError, AttributeError):
            blocked = False
        if not blocked:
            raise StateError('COMPARISON_RETRY_EXTERNAL_RESULT_NOT_BLOCKED')
    errors = saved.get('final_validation_errors', [])
    if not errors:
        schema = RESULT_SCHEMAS[f'{role}.{task}' if role == 'discovery' else role]
        try:
            Envelope[schema].model_validate_json(raw)
        except ValidationError as exc:
            errors = output_validation_errors(raw, Envelope[schema], exc)
    replacement_key = f'{task_key}.protocol_retry{len(history) + 1}'
    path = f'evaluations/{source_run_id}/task-retries/{system}.{replacement_key}.json'
    audit = {'source_run_id': source_run_id, 'run_id': run_id, 'system': system,
        'task_key': task_key, 'replacement_key': replacement_key,
        'source_task_id': source.task_id, 'source_response_artifact_path': source.response_artifact_path,
        'source_rendered_prompt_path': source.rendered_prompt_path, 'frozen_material_path': frozen_path,
        'subject': subject, 'budget_account_id': run.budget_account_id,
        'reason': reason.strip(), 'requested_at': utc_now(), 'trigger': 'explicit_user_command',
        'superseded_cached_envelope': cached,
        'protocol_retry': {'previous_task_id': source.task_id,
            'previous_error': source.error or run.stop_reason,
            'validation_errors': errors, 'unaccepted_response': raw,
            'previous_successful_tools': []}}
    audit = json.loads(json.dumps(audit, ensure_ascii=False, default=str))
    try:
        previous = json.loads(store.read_artifact(path))
    except FileNotFoundError:
        store.save_artifact(path, json.dumps(audit, ensure_ascii=False, sort_keys=True))
    else:
        if {k:v for k,v in previous.items() if k != 'requested_at'} != {
                k:v for k,v in audit.items() if k != 'requested_at'}:
            raise StateError('COMPARISON_RETRY_ARTIFACT_CONFLICT')
        audit = previous
    entry = {k:audit[k] for k in ('source_task_id', 'replacement_key', 'reason', 'requested_at')}
    entry['audit_path'] = path
    history.append(entry)
    retries[task_key] = history
    envelopes.pop(task_key, None)
    store.update_run(run_id, status='RUNNING', stop_reason=None, state={**run.state,
        'comparison_task_retries': retries, 'comparison_envelopes': envelopes})
    return entry
