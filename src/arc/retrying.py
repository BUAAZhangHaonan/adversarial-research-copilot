"""Explicit user-triggered task revisions; never automatic model retry loops."""
from __future__ import annotations
import json
from pydantic import ValidationError
from .schemas import Envelope, RESULT_SCHEMAS, utc_now
from .store import StateError
from .validation import output_validation_errors


def prepare_task_retry(store, ledger, run_id, task_key, reason):
    run = store.get_run(run_id)
    if run.status != 'PAUSED_PROTOCOL' or not reason.strip():
        raise StateError('TASK_RETRY_REQUIRES_PROTOCOL_PAUSE_AND_REASON')
    if any(c['state'] not in ('SETTLED', 'NOT_SENT') for c in ledger.list_calls(run.budget_account_id)):
        raise StateError('TASK_RETRY_HAS_UNSETTLED_CALLS')
    if task_key not in run.state.get('task_inputs', {}):
        raise StateError('TASK_RETRY_REQUIRES_UNACCEPTED_TASK_KEY')
    retries = dict(run.state.get('task_retries', {}))
    history = list(retries.get(task_key, []))
    source_key = history[-1]['replacement_key'] if history else task_key
    source = store.get_task(f'{run_id}.{source_key}')
    application_failure = None
    if task_key in run.state:
        cached = run.state[task_key]
        current = store.get_card(run.card_id, run.card_version).draft.problem_anchor.model_dump(mode='json')
        proposed = cached.get('proposed_card_revision') if isinstance(cached, dict) else None
        if (run.stop_reason != 'problem_anchor_changed' or source is None
                or source.status != 'ACCEPTED' or not source.accepted_result
                or source.accepted_result.get('result') != cached or not proposed
                or proposed.get('problem_anchor') == current):
            raise StateError('TASK_RETRY_REQUIRES_UNACCEPTED_TASK_KEY')
        application_failure = {'type': 'problem_anchor_changed',
            'loc': ['result', 'proposed_card_revision', 'problem_anchor'],
            'expected': current, 'submitted': proposed.get('problem_anchor')}
    if (source is None or (not application_failure and (source.status != 'PAUSED_PROTOCOL'
            or source.accepted_result is not None))
            or not source.response_artifact_path or not source.rendered_prompt_path):
        raise StateError('TASK_RETRY_REQUIRES_FAILED_TASK_RECORD')
    original_input = run.state['task_inputs'][task_key]
    subject = original_input['subject']
    if (subject.get('run_id'), subject.get('card_id'), subject.get('card_version')) != (
            run_id, run.card_id, run.card_version):
        raise StateError('TASK_RETRY_SUBJECT_CHANGED')
    snapshot = json.loads(store.read_artifact(source.rendered_prompt_path))
    role, task = snapshot['prompt_id'].split('.', 1)
    result_schema = RESULT_SCHEMAS[f'{role}.{task}' if role == 'discovery' else role]
    envelope_type = Envelope[result_schema]
    saved = json.loads(store.read_artifact(source.response_artifact_path))
    raw = ((saved.get('response') or {}).get('message') or {}).get('content') or ''
    if application_failure and role != 'moderator':
        raise StateError('TASK_RETRY_APPLICATION_ROLE_MISMATCH')
    errors = [application_failure] if application_failure else saved.get('final_validation_errors', [])
    if not errors:
        try:
            envelope_type.model_validate_json(raw)
        except ValidationError as exc:
            errors = output_validation_errors(raw, envelope_type, exc)
    successful_tools = []
    for identifier in dict.fromkeys([item['source_task_id'] for item in history] + [source.task_id]):
        prior = store.get_task(identifier)
        prior_state = json.loads(store.read_artifact(prior.response_artifact_path))
        successful_tools.extend(item for item in prior_state.get('tool_trace', [])
                                if item.get('status') == 'completed')
    number = len(history) + 1
    replacement_key = f'{task_key}.protocol_retry{number}'
    path = f'runs/{run_id}/task-retries/{replacement_key}.json'
    audit = {'run_id': run_id, 'task_key': task_key, 'source_task_id': source.task_id,
             'source_response_artifact_path': source.response_artifact_path,
             'replacement_key': replacement_key, 'role': role, 'task': task,
             'reason': reason.strip(), 'requested_at': utc_now(), 'trigger': 'explicit_user_command',
             'budget_account_id': run.budget_account_id, 'original_input': original_input,
             'tool_profile': [t['function']['name'] for t in saved.get('original_tools', [])],
             'application_failure': application_failure,
             'superseded_cached_result': run.state.get(task_key),
             'protocol_retry': {'previous_task_id': source.task_id, 'previous_error': source.error or run.stop_reason,
                 'validation_errors': errors, 'unaccepted_response': raw,
                 'previous_successful_tools': successful_tools}}
    audit = json.loads(json.dumps(audit, ensure_ascii=False, default=str))
    try:
        previous = json.loads(store.read_artifact(path))
    except FileNotFoundError:
        store.save_artifact(path, json.dumps(audit, ensure_ascii=False, sort_keys=True))
    else:
        if {k:v for k,v in previous.items() if k != 'requested_at'} != {
                k:v for k,v in audit.items() if k != 'requested_at'}:
            raise StateError('TASK_RETRY_ARTIFACT_CONFLICT')
        audit = previous
    history.append({k:audit[k] for k in ('source_task_id','replacement_key','role','task','reason','requested_at')}
                   | {'audit_path': path})
    retries[task_key] = history
    updated_state = {**run.state, 'task_retries': retries}
    if application_failure:
        for field in (task_key, task_key + '_trace_tasks', task_key + '_evidence_requests'):
            updated_state.pop(field, None)
    store.update_run(run_id, status='RUNNING', stop_reason=None, state=updated_state)
    return history[-1]
