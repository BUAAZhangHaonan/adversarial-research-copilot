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
    if task_key in run.state or task_key not in run.state.get('task_inputs', {}):
        raise StateError('TASK_RETRY_REQUIRES_UNACCEPTED_TASK_KEY')
    retries = dict(run.state.get('task_retries', {}))
    history = list(retries.get(task_key, []))
    source_key = history[-1]['replacement_key'] if history else task_key
    source = store.get_task(f'{run_id}.{source_key}')
    if (source is None or source.status != 'PAUSED_PROTOCOL' or source.accepted_result is not None
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
    errors = saved.get('final_validation_errors', [])
    if not errors:
        try:
            envelope_type.model_validate_json(raw)
        except ValidationError as exc:
            errors = output_validation_errors(raw, envelope_type, exc)
    number = len(history) + 1
    replacement_key = f'{task_key}.protocol_retry{number}'
    path = f'runs/{run_id}/task-retries/{replacement_key}.json'
    audit = {'run_id': run_id, 'task_key': task_key, 'source_task_id': source.task_id,
             'source_response_artifact_path': source.response_artifact_path,
             'replacement_key': replacement_key, 'role': role, 'task': task,
             'reason': reason.strip(), 'requested_at': utc_now(), 'trigger': 'explicit_user_command',
             'budget_account_id': run.budget_account_id, 'original_input': original_input,
             'tool_profile': [t['function']['name'] for t in saved.get('original_tools', [])],
             'protocol_retry': {'previous_task_id': source.task_id, 'previous_error': source.error,
                 'validation_errors': errors, 'unaccepted_response': raw,
                 'previous_successful_tools': [t for t in saved.get('tool_trace', [])
                                               if t.get('status') == 'completed']}}
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
    store.update_run(run_id, status='RUNNING', stop_reason=None,
                     state={**run.state, 'task_retries': retries})
    return history[-1]
