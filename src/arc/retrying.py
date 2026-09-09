"""Explicit user-triggered task revisions; never automatic model retry loops."""
from __future__ import annotations
import copy
import json
import re
from pydantic import ValidationError
from .schemas import Envelope, RESULT_SCHEMAS, utc_now
from .store import StateError
from .validation import output_validation_errors


def retry_working_view(protocol_retry, *, audit_path=None):
    """Condense repetitive empty cache reads for a new task, preserving its audit."""
    view = copy.deepcopy(protocol_retry)
    refreshed = view.pop('refreshed_validation_errors', None)
    if refreshed is not None:
        view['validation_errors'] = refreshed
        if audit_path is not None:
            view['original_validation_errors_audit_path'] = audit_path
    retained, boundaries = [], {}
    for item in view.get('previous_successful_tools', []):
        result = item.get('result') or {}
        arguments = item.get('arguments') or {}
        source_id = result.get('source_id') or arguments.get('record_id')
        empty_boundary = (item.get('name') == 'read_record' and source_id
            and result.get('content') == ''
            and result.get('content_origin') != 'metadata'
            and result.get('access_status') != 'metadata_only'
            and (result.get('requires_source_fetch') is True
                 or result.get('error') in {'SOURCE_CACHE_EXHAUSTED', 'SOURCE_END_REACHED'}))
        if not empty_boundary:
            retained.append(item)
            continue
        summary = boundaries.setdefault(source_id, {'source_id': source_id,
            'omitted_empty_reads': 0})
        summary['omitted_empty_reads'] += 1
        summary.update({key: result[key] for key in (
            'url', 'cached_content_chars', 'content_total_chars', 'content_complete',
            'requires_source_fetch', 'cached_range_start', 'cached_range_end') if key in result})
        summary['error'] = result.get('error') or 'SOURCE_CACHE_EXHAUSTED'
        summary['next_cached_offset'] = None
    view['previous_successful_tools'] = retained
    if boundaries:
        view['previous_source_read_boundaries'] = list(boundaries.values())
        if audit_path is not None:
            view['previous_successful_tools_audit_path'] = audit_path
    return view


def _confirmed_rejected_call(store, call, run_id):
    """Allow explicit retry of a received HTTP 400, never of an unknown response."""
    metadata = call.get('metadata') or {}
    if (call.get('state') != 'UNKNOWN' or metadata.get('run_id') != run_id
            or not metadata.get('model_requested') or metadata.get('error') != 'BadRequestError'):
        return None
    task = store.get_task(metadata.get('task_id', ''))
    if (task is None or task.run_id != run_id or task.status != 'UNKNOWN'
            or task.error != 'BadRequestError' or task.accepted_result is not None
            or not task.response_artifact_path):
        return None
    saved = json.loads(store.read_artifact(task.response_artifact_path))
    if saved.get('partial_chunks') != [] or saved.get('pending_model') != call['call_id']:
        return None
    if (saved.get('response') or {}).get('call_id') == call['call_id']:
        return None
    request_error = saved.get('request_error')
    if request_error is not None and (request_error.get('type') != 'BadRequestError'
                                     or request_error.get('status_code') != 400):
        return None
    return {'call_id': call['call_id'], 'task_id': task.task_id,
        'error': 'BadRequestError', 'http_status': 400, 'partial_chunk_count': 0,
        'basis': 'saved_http_status' if request_error is not None else 'legacy_sdk_bad_request_type',
        'ledger_state_preserved': 'UNKNOWN', 'response_artifact_path': task.response_artifact_path}


def _last_settled_task_response(store, calls, task_id):
    """Recover the draft preceding a rejected correction from this task only."""
    for call in reversed(calls):
        metadata = call.get('metadata') or {}
        path = metadata.get('response_artifact_path')
        if (call.get('state') != 'SETTLED' or metadata.get('task_id') != task_id
                or not metadata.get('model_requested') or not path):
            continue
        state = json.loads(store.read_artifact(path))
        response = state.get('response') or {}
        raw = (response.get('message') or {}).get('content')
        if response.get('call_id') == call['call_id'] and response.get('finish_reason') == 'stop' and raw:
            return raw, {'call_id': call['call_id'], 'response_artifact_path': path}
    return '', None


def _refreshed_reference_errors(store, errors, payload, tools):
    """Replace only diagnostic displays, leaving raw outputs and audit errors intact."""
    from .runtime import reference_ids, SOURCE_REF_KEYS, EVIDENCE_REF_KEYS
    from .validation import output_reference_diagnostics
    visible = {kind: reference_ids([payload, tools], keys) for kind, keys in
        [('source', SOURCE_REF_KEYS), ('evidence', EVIDENCE_REF_KEYS)]}
    refreshed, changed = [], False
    marker = 'OUTPUT_REFERENCE_INVALID; '
    for error in errors:
        if not isinstance(error, str) or marker not in error:
            refreshed.append(error)
            continue
        prefix, serialized = error.split(marker, 1)
        try:
            previous = json.loads(serialized)
        except ValueError:
            refreshed.append(error)
            continue
        entries = previous.get('errors', []) if isinstance(previous, dict) else previous
        if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
            refreshed.append(error)
            continue
        entries = copy.deepcopy(entries)
        for item in entries:
            item.pop('visible_candidates', None)
            if 'reference_kind' not in item:
                item['reference_kind'] = ('evidence' if any(part in EVIDENCE_REF_KEYS
                    for part in item.get('loc', []) if isinstance(part, str)) else 'source')
        diagnostics = output_reference_diagnostics(store, entries, visible)
        refreshed.append(prefix + marker + json.dumps(diagnostics, ensure_ascii=False))
        changed = True
    return refreshed if changed else None


def prepare_task_retry(store, ledger, run_id, task_key, reason):
    run = store.get_run(run_id)
    if run.status not in {'PAUSED_PROTOCOL', 'PAUSED_EXTERNAL'} or not reason.strip():
        raise StateError('TASK_RETRY_REQUIRES_PROTOCOL_PAUSE_AND_REASON')
    calls = ledger.list_calls(run.budget_account_id)
    rejected_calls = []
    for call in calls:
        if call['state'] in ('SETTLED', 'NOT_SENT'):
            continue
        rejected = _confirmed_rejected_call(store, call, run_id)
        if rejected is None:
            raise StateError('TASK_RETRY_HAS_UNSETTLED_CALLS')
        rejected_calls.append(rejected)
    if task_key not in run.state.get('task_inputs', {}):
        raise StateError('TASK_RETRY_REQUIRES_UNACCEPTED_TASK_KEY')
    retries = dict(run.state.get('task_retries', {}))
    history = list(retries.get(task_key, []))
    source_key = history[-1]['replacement_key'] if history else task_key
    source = store.get_task(f'{run_id}.{source_key}')
    rejected_source = source is not None and any(item['task_id'] == source.task_id for item in rejected_calls)
    if run.status == 'PAUSED_EXTERNAL' and not rejected_source:
        raise StateError('TASK_RETRY_REQUIRES_CONFIRMED_REQUEST_REJECTION')
    application_failure = None
    issue_application_retry = False
    prior_input = run.state['task_inputs'].get(source_key, run.state['task_inputs'][task_key])
    pending = run.state.get('pending_issue_application_retry')
    resumed_issue_application = bool(history and pending and pending.get('task_key') == task_key)
    if resumed_issue_application:
        pending_audit = json.loads(store.read_artifact(pending['audit_path']))
        frozen = pending_audit['original_input']
        card = store.get_card(run.card_id, run.card_version)
        expected_subject = (run_id, run.card_id, run.card_version)
        if (pending['round'] != int(run.state.get('rounds_completed', 0)) + 1
                or pending_audit['run_id'] != run_id or pending_audit['task_key'] != task_key
                or pending_audit['application_failure']['type'] != 'empirical_resolution_requires_verified_claim_evidence'
                or tuple(frozen['subject'].get(k) for k in ('run_id', 'card_id', 'card_version')) != expected_subject
                or tuple(prior_input['subject'].get(k) for k in ('run_id', 'card_id', 'card_version')) != expected_subject
                or frozen['payload']['card'] != card.model_dump(mode='json')):
            raise StateError('TASK_RETRY_APPLIED_CARD_MISMATCH')
    if task_key in run.state:
        cached = run.state[task_key]
        current = store.get_card(run.card_id, run.card_version).draft.problem_anchor.model_dump(mode='json')
        proposed = cached.get('proposed_card_revision') if isinstance(cached, dict) else None
        if (source is None
                or source.status != 'ACCEPTED' or not source.accepted_result
                or source.accepted_result.get('result') != cached):
            raise StateError('TASK_RETRY_REQUIRES_UNACCEPTED_TASK_KEY')
        if run.stop_reason == 'problem_anchor_changed' and proposed and proposed.get('problem_anchor') != current:
            application_failure = {'type': 'problem_anchor_changed',
                'loc': ['result', 'proposed_card_revision', 'problem_anchor'],
                'expected': current, 'submitted': proposed.get('problem_anchor')}
        elif run.stop_reason == 'empirical_resolution_requires_verified_claim_evidence':
            match = re.fullmatch(r'round(\d+)\.moderator(?:\.evidence_reassessment)?', task_key)
            number = int(match[1]) if match else None
            base = f'round{number}.moderator'
            pending_key = base + '.evidence_reassessment' if base + '.evidence_reassessment' in run.state else base
            if number != int(run.state.get('rounds_completed', 0)) + 1 or task_key != pending_key:
                raise StateError('TASK_RETRY_NOT_PENDING_ISSUE_RULING')
            card = store.get_card(run.card_id, run.card_version)
            old_subject = prior_input['subject']
            if resumed_issue_application:
                if (proposed is not None or cached.get('direction_change') is not None
                        or source.accepted_result.get('subject') != old_subject):
                    raise StateError('TASK_RETRY_APPLIED_CARD_MISMATCH')
            else:
                creation_key = (f'{run_id}.{source_key}.revision' if history else
                    f'{run_id}.round{number}' + ('.evidence_reassessment' if task_key.endswith('.evidence_reassessment') else '') + '.revision')
                with store._connect() as db:
                    created = db.execute('SELECT card_id,version FROM card_creation WHERE creation_key=?',
                        (creation_key,)).fetchone()
                if (not proposed or old_subject.get('run_id') != run_id
                        or old_subject.get('card_id') != run.card_id
                        or card.parent_version != old_subject.get('card_version')
                        or created is None or (created['card_id'], created['version']) != (run.card_id, run.card_version)
                        or card.draft.model_dump(mode='json') != proposed):
                    raise StateError('TASK_RETRY_APPLIED_CARD_MISMATCH')
            try:
                store.apply_issues(run_id, cached['updated_issues'], cached['issue_transitions'], dry_run=True)
            except StateError as exc:
                if str(exc) != run.stop_reason:
                    raise StateError('TASK_RETRY_APPLICATION_FAILURE_CHANGED') from exc
                application_failure = {'type': str(exc), 'diagnostics': getattr(exc, 'diagnostics', [])}
            else:
                raise StateError('TASK_RETRY_APPLICATION_FAILURE_NOT_REPRODUCED')
            issue_application_retry = True
            round_number = number
            application_failure['correction_scope'] = {
                'proposed_card_revision': None,
                'instruction': 'Preserve the already saved current card. Correct only issue evidence references and issue status/ruling as justified by current registered evidence; return proposed_card_revision=null. Do not change claim text, conditions, versions, or research scope.'}
        else:
            raise StateError('TASK_RETRY_REQUIRES_UNACCEPTED_TASK_KEY')
    if (source is None or (not application_failure and ((source.status != 'PAUSED_PROTOCOL' and not rejected_source)
            or source.accepted_result is not None))
            or not source.response_artifact_path or not source.rendered_prompt_path):
        raise StateError('TASK_RETRY_REQUIRES_FAILED_TASK_RECORD')
    original_input = prior_input if resumed_issue_application else run.state['task_inputs'][task_key]
    if issue_application_retry:
        from .workflows import WorkflowEngine
        context = WorkflowEngine(store, None, None).context(run_id)
        original_input = {'payload': {**prior_input['payload'], **context}, 'subject': context['subject']}
    subject = original_input['subject']
    if (subject.get('run_id'), subject.get('card_id'), subject.get('card_version')) != (
            run_id, run.card_id, run.card_version):
        raise StateError('TASK_RETRY_SUBJECT_CHANGED')
    snapshot = json.loads(store.read_artifact(source.rendered_prompt_path))
    role, task = snapshot['prompt_id'].split('.', 1)
    result_schema = RESULT_SCHEMAS[f'{role}.{task}' if f'{role}.{task}' in RESULT_SCHEMAS else role]
    envelope_type = Envelope[result_schema]
    saved = json.loads(store.read_artifact(source.response_artifact_path))
    raw = ((saved.get('response') or {}).get('message') or {}).get('content') or ''
    recovered_draft = None
    if rejected_source and not raw:
        raw, recovered_draft = _last_settled_task_response(store, calls, source.task_id)
    if (application_failure or resumed_issue_application) and role != 'moderator':
        raise StateError('TASK_RETRY_APPLICATION_ROLE_MISMATCH')
    errors = [application_failure] if application_failure else (saved.get('final_validation_errors') or saved.get('repair_validation_errors', []))
    if not errors:
        try:
            envelope_type.model_validate_json(raw)
        except ValidationError as exc:
            errors = output_validation_errors(raw, envelope_type, exc)
    if resumed_issue_application and not application_failure:
        errors = [*errors, {'type': 'empirical_application_correction_scope',
            **pending_audit['application_failure']['correction_scope']}]
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
             'previous_input': prior_input,
             'tool_profile': [t['function']['name'] for t in saved.get('original_tools', [])],
             'application_failure': application_failure,
             'superseded_cached_result': run.state.get(task_key),
             'protocol_retry': {'request_reason': reason.strip(),
                 'previous_task_id': source.task_id, 'previous_error': source.error or run.stop_reason,
                 'validation_errors': errors, 'unaccepted_response': raw,
                 'previous_successful_tools': successful_tools}}
    refreshed = _refreshed_reference_errors(store, errors, original_input['payload'], successful_tools)
    if refreshed is not None:
        audit['protocol_retry']['refreshed_validation_errors'] = refreshed
    if rejected_calls:
        audit['confirmed_rejected_calls'] = rejected_calls
    if recovered_draft:
        audit['recovered_unaccepted_response'] = recovered_draft
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
    if issue_application_retry:
        updated_state['pending_issue_application_retry'] = {'task_key': task_key,
            'round': round_number, 'audit_path': path}
    if application_failure:
        for field in (task_key, task_key + '_trace_tasks', task_key + '_evidence_requests'):
            updated_state.pop(field, None)
    store.update_run(run_id, status='RUNNING', stop_reason=None, state=updated_state)
    return history[-1]
