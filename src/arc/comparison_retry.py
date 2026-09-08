"""Explicit revisions of failed frozen-comparison tasks, preserving prior results."""
from __future__ import annotations

import json
import re
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


def comparison_retry_options(task_key):
    """Recover the exact seeded presentation selected by the explicit task key."""
    match = re.fullmatch(r'judge\.seed(-?\d+)\.(forward|swapped)', task_key)
    if not match:
        return {}
    seed, order = int(match[1]), match[2]
    if str(seed) != match[1] or (seed == 20260907 and order == 'forward'):
        raise StateError('COMPARISON_RETRY_INVALID_SYSTEM_TASK_OR_REASON')
    return {'seed': seed, 'include_swapped_order': order == 'swapped'}


def frozen_reference_diagnostics(raw, material):
    """Locate invalid reference values without editing or suggesting a replacement."""
    from .runtime import EVIDENCE_REF_KEYS, SOURCE_REF_KEYS
    try:
        response = json.loads(raw)
    except ValueError:
        return [], None
    evidence = material.get('evidence', [])
    sources = material.get('sources', [])
    allowed = {'evidence': {item['evidence_id'] for item in evidence},
               'source': {item['source_id'] for item in sources}}
    errors = []

    def visit(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                kind = 'evidence' if key in EVIDENCE_REF_KEYS else 'source' if key in SOURCE_REF_KEYS else None
                if kind is not None:
                    references = list(enumerate(item)) if isinstance(item, list) else [(None, item)]
                    for index, reference in references:
                        if isinstance(reference, str) and reference not in allowed[kind]:
                            errors.append({'type': 'reference_not_in_frozen_material',
                                'loc': path + [key] + ([index] if index is not None else []),
                                'reference_kind': kind, 'submitted_value': reference,
                                'msg': 'The supplied frozen material does not contain this reference ID.',
                                'feedback_only': True})
                else:
                    visit(item, path + [key])
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, path + [index])

    visit(response, [])
    catalog = {'evidence': [{k: item.get(k) for k in ('evidence_id', 'claim_id', 'source_id')}
                            for item in evidence],
               'source_ids': sorted(allowed['source'])} if errors else None
    return errors, catalog


def prepare_comparison_retry(store, ledger, source_run_id, system, task_key, reason):
    return _prepare_comparison_retry(store, ledger, source_run_id, system, task_key, reason)


def prepare_ablation_selection_retry(store, ledger, experiment_id, condition, reason):
    """Explicitly correct an ablation selector application failure; never redraw."""
    return _prepare_comparison_retry(store, ledger, experiment_id, condition, 'selection', reason,
                                     ablation=True)


def _prepare_comparison_retry(store, ledger, source_run_id, system, task_key, reason, *, ablation=False):
    """Record one user request; only execution creates the new physical task."""
    options = comparison_retry_options(task_key)
    spec = ('evaluator', 'INVOKE') if options else COMPARISON_TASKS.get(task_key)
    if system not in (('A', 'B', 'C') if ablation else ('ARC', 'direct-Pro', 'evaluator')) or spec is None or not reason.strip():
        raise StateError('COMPARISON_RETRY_INVALID_SYSTEM_TASK_OR_REASON')
    if ((system == 'evaluator') != (spec[0] == 'evaluator')
            or (system == 'direct-Pro' and task_key in ('frame', 'family'))):
        raise StateError('COMPARISON_RETRY_TASK_NOT_IN_SYSTEM')
    run_id = source_run_id + ('.' if ablation else '.comparison.') + system
    run = store.get_run(run_id)
    if run.mode != 'evaluation' or run.status not in ('PAUSED_PROTOCOL', 'PAUSED_EXTERNAL'):
        raise StateError('COMPARISON_RETRY_REQUIRES_FAILED_OR_BLOCKED_RUN')
    if any(c['state'] not in ('SETTLED', 'NOT_SENT') for c in ledger.list_calls(run.budget_account_id)):
        raise StateError('COMPARISON_RETRY_HAS_UNSETTLED_CALLS')
    frozen_path = (f'functional-evaluations/{source_run_id}/manifest.json' if ablation else
                   f'evaluations/{source_run_id}/evidence.json')
    frozen = json.loads(store.read_artifact(frozen_path))
    material = frozen.get('material', {})
    if ablation and (run.status != 'PAUSED_PROTOCOL'
            or run.state.get('functional_experiment') != source_run_id
            or run.state.get('condition') != system or run.state.get('material_path') != frozen_path
            or frozen.get('experiment_id') != source_run_id
            or ledger.summary(run.budget_account_id)['parent_id'] != frozen.get('parent_id')
            or 'functional_result' in run.state):
        raise StateError('ABLATION_SELECTION_RETRY_BINDING_MISMATCH')
    retries = dict(run.state.get('comparison_task_retries', {}))
    history = list(retries.get(task_key, []))
    previous_key = history[-1]['replacement_key'] if history else task_key
    source = store.get_task(f'{run_id}.{previous_key}')
    envelopes = dict(run.state.get('comparison_envelopes', {}))
    cached = envelopes.get(task_key)
    application_failure = None
    if ablation:
        from .schemas import NoveltyResult, SelectorResult
        from .validation import validate_selection, ProtocolViolation
        original_input = run.state.get('task_inputs', {}).get('selection', {})
        payload = original_input.get('payload', {})
        current_subject = {'campaign_id': run.campaign_id, 'run_id': run_id,
            'card_id': run.card_id, 'card_version': run.card_version}
        card = store.get_card(run.card_id, run.card_version)
        if (original_input.get('subject') != current_subject
                or payload.get('card') != card.model_dump(mode='json')
                or payload.get('novelty') != envelopes.get('novelty', {}).get('result')):
            raise StateError('ABLATION_SELECTION_RETRY_INPUT_CHANGED')
        if source is not None and source.status == 'ACCEPTED':
            if (source.run_id != run_id or not cached or cached.get('task_id') != source.task_id
                    or source.accepted_result != cached
                    or cached.get('result_status') != 'complete' or cached.get('subject') != current_subject):
                raise StateError('ABLATION_SELECTION_RETRY_ACCEPTED_CACHE_MISMATCH')
            try:
                validate_selection(store, card, SelectorResult.model_validate(cached['result']),
                                   NoveltyResult.model_validate(payload['novelty']))
            except ProtocolViolation as exc:
                diagnostics = json.loads(str(exc))
                if run.stop_reason != str(exc) and run.stop_reason not in {d['type'] for d in diagnostics}:
                    raise StateError('ABLATION_SELECTION_RETRY_FAILURE_CHANGED') from exc
                application_failure = {'type': 'ablation_selection_application_failure',
                                       'validation_errors': diagnostics}
            else:
                raise StateError('ABLATION_SELECTION_RETRY_FAILURE_NOT_REPRODUCED')
        elif history and cached is None:
            previous_audit = json.loads(store.read_artifact(history[-1]['audit_path']))
            application_failure = previous_audit.get('application_failure')
            if not application_failure or application_failure.get('type') != 'ablation_selection_application_failure':
                raise StateError('ABLATION_SELECTION_RETRY_REQUIRES_APPLICATION_HISTORY')
        else:
            raise StateError('ABLATION_SELECTION_RETRY_REQUIRES_ACCEPTED_APPLICATION_FAILURE')
    accepted_application = ablation and source is not None and source.status == 'ACCEPTED'
    if (source is None or (not accepted_application and
            (source.status not in ('PAUSED_PROTOCOL', 'PAUSED_EXTERNAL') or source.accepted_result is not None))
            or not source.response_artifact_path or not source.rendered_prompt_path):
        raise StateError('COMPARISON_RETRY_REQUIRES_UNACCEPTED_FAILED_TASK')
    if cached is not None and cached.get('result_status') == 'complete' and not accepted_application:
        raise StateError('COMPARISON_RETRY_CANNOT_REPLACE_COMPLETED_RESULT')
    role, task = spec
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
    if accepted_application and json.loads(raw) != source.accepted_result:
        raise StateError('ABLATION_SELECTION_RETRY_RAW_MISMATCH')
    errors = (application_failure['validation_errors'] if accepted_application else
              saved.get('final_validation_errors', []))
    if not errors:
        schema = RESULT_SCHEMAS[f'{role}.{task}' if role == 'discovery' else role]
        try:
            Envelope[schema].model_validate_json(raw)
        except ValidationError as exc:
            errors = output_validation_errors(raw, Envelope[schema], exc)
    reference_errors, reference_catalog = frozen_reference_diagnostics(raw, material)
    errors = [*errors, *reference_errors]
    replacement_key = f'{task_key}.protocol_retry{len(history) + 1}'
    path = (f'functional-evaluations/{source_run_id}/task-retries/{system}.{replacement_key}.json' if ablation else
            f'evaluations/{source_run_id}/task-retries/{system}.{replacement_key}.json')
    audit = {'source_run_id': source_run_id, 'run_id': run_id, 'system': system,
        'task_key': task_key, 'replacement_key': replacement_key,
        'source_task_id': source.task_id, 'source_response_artifact_path': source.response_artifact_path,
        'source_rendered_prompt_path': source.rendered_prompt_path, 'frozen_material_path': frozen_path,
        'subject': subject, 'budget_account_id': run.budget_account_id,
        'reason': reason.strip(), 'requested_at': utc_now(), 'trigger': 'explicit_user_command',
        'superseded_cached_envelope': cached,
        'protocol_retry': {'previous_task_id': source.task_id,
            'previous_error': source.error or run.stop_reason,
            'request_reason': reason.strip(),
            'validation_errors': errors, 'unaccepted_response': raw,
            'previous_successful_tools': []}}
    if application_failure is not None:
        audit['application_failure'] = application_failure
        audit['protocol_retry']['application_failure'] = application_failure
        audit['protocol_retry']['previous_response_was_accepted'] = accepted_application
    if reference_catalog is not None:
        audit['protocol_retry']['frozen_reference_catalog'] = reference_catalog
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
