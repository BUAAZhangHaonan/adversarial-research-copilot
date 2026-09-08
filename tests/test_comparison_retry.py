"""Frozen comparison retries change only an explicitly failed physical task."""
from __future__ import annotations

import copy
import json

import pytest
from typer.testing import CliRunner

from arc.budget import BudgetLedger
from arc.cli import app
from arc.comparison_retry import frozen_reference_diagnostics, prepare_comparison_retry, comparison_retry_options
from arc.evaluation import VALIDATION_PARENT, _frozen_call, run_comparison
from arc.schemas import TaskRecord
from arc.store import StateError
from tests.test_evaluation import ComparisonRuntime, environment


REASON = 'User requests fixing this failed structural output while preserving the frozen study.'


def failed_record(store, run, key='compose', *, status='PAUSED_PROTOCOL', cached=None):
    task_id = f'{run.run_id}.{key}'
    subject = {'campaign_id': run.campaign_id, 'run_id': run.run_id,
               'card_id': run.card_id, 'card_version': run.card_version}
    raw = json.dumps(cached) if cached is not None else '{"result": {"unexpected": true}}'
    prompt = store.save_artifact(f'tests/{task_id}.prompt.json', json.dumps({
        'prompt_id': 'evaluator.INVOKE' if key.startswith('judge') else
            {'frame': 'discovery.FRAME', 'compose': 'discovery.COMPOSE'}[key]}))
    response = store.save_artifact(f'tests/{task_id}.failed.json', json.dumps({
        'subject': subject, 'response': {'message': {'content': raw}},
        'original_tools': [], 'tool_trace': [],
        'repair_counts': {'output_json': 1, 'tool_arguments': 0}}))
    task = TaskRecord(task_id=task_id, run_id=run.run_id, input_hash='test-input',
        prompt_hash='test-prompt', model_config_hash='test-model', status=status,
        error='INVALID_OUTPUT_AFTER_REPAIR' if status == 'PAUSED_PROTOCOL' else None,
        rendered_prompt_path=prompt, response_artifact_path=response)
    store.put_task(task)
    state = copy.deepcopy(run.state)
    if cached is not None:
        state.setdefault('comparison_envelopes', {})[key] = cached
    store.update_run(run.run_id, status=status, state=state,
        stop_reason=task.error or 'frozen_material_blocked')
    return store.get_task(task_id)


async def setup_failed_comparison(tmp_path, monkeypatch):
    import arc.bootstrap
    settings, store, source, calls = environment(tmp_path, monkeypatch)
    async def make_runtime(store, ledger, run, settings):
        return ComparisonRuntime(store, calls, fail=run.run_id.endswith('.ARC'))
    monkeypatch.setattr(arc.bootstrap, 'make_runtime', make_runtime)
    await run_comparison(settings, source.run_id)
    run = store.get_run(source.run_id + '.comparison.ARC')
    task = failed_record(store, run)
    ledger = BudgetLedger(store.db_path)
    return settings, store, source, calls, ledger, store.get_run(run.run_id), task


@pytest.mark.asyncio
async def test_retry_preserves_old_failure_material_completed_candidate_and_accounting(tmp_path, monkeypatch):
    import arc.bootstrap
    settings, store, source, calls, ledger, run, task = await setup_failed_comparison(tmp_path, monkeypatch)
    original = task.model_dump(mode='json')
    raw = store.read_artifact(task.response_artifact_path)
    frozen_path = f'evaluations/{source.run_id}/evidence.json'
    frozen = store.read_artifact(frozen_path)
    envelopes = copy.deepcopy(run.state['comparison_envelopes'])
    baseline = store.get_run(source.run_id + '.comparison.direct-Pro')
    baseline_card = store.get_card(baseline.card_id, baseline.card_version).model_dump(mode='json')
    old_calls = ledger.list_calls()
    budget = ledger.summary(VALIDATION_PARENT)
    entry = prepare_comparison_retry(store, ledger, source.run_id, 'ARC', 'compose', REASON)
    assert entry['replacement_key'] == 'compose.protocol_retry1'
    assert store.get_task(task.task_id).model_dump(mode='json') == original
    assert store.read_artifact(task.response_artifact_path) == raw
    assert ledger.list_calls() == old_calls and ledger.summary(VALIDATION_PARENT) == budget
    audit = json.loads(store.read_artifact(entry['audit_path']))
    assert audit['protocol_retry']['validation_errors']
    assert audit['protocol_retry']['unaccepted_response'] == json.loads(raw)['response']['message']['content']
    assert audit['frozen_material_path'] == frozen_path
    assert audit['budget_account_id'] == run.budget_account_id
    count = len(calls)
    async def repaired(store, ledger, run, settings):
        return ComparisonRuntime(store, calls)
    monkeypatch.setattr(arc.bootstrap, 'make_runtime', repaired)
    result = await run_comparison(settings, source.run_id)
    assert result['comparison_status'] == 'completed'
    new_calls = calls[count:]
    assert [c['task_id'].rsplit('.', 1)[-1] for c in new_calls] == [
        'protocol_retry1', 'novelty', 'selection', 'judge']
    assert all(c['tools'] == [] for c in new_calls)
    assert new_calls[0]['payload']['protocol_retry'] == audit['protocol_retry']
    assert store.read_artifact(frozen_path) == frozen
    assert store.get_task(task.task_id).model_dump(mode='json') == original
    assert store.get_card(baseline.card_id, baseline.card_version).model_dump(mode='json') == baseline_card
    latest = store.get_run(run.run_id)
    assert all(latest.state['comparison_envelopes'][k] == v for k, v in envelopes.items())
    count = len(calls)
    await run_comparison(settings, source.run_id)
    assert len(calls) == count


@pytest.mark.asyncio
async def test_blocked_cached_frame_is_audited_not_silently_reused(tmp_path, monkeypatch):
    import arc.cli
    settings, store, source, calls = environment(tmp_path, monkeypatch)
    ledger = BudgetLedger(store.db_path)
    ledger.create_account(VALIDATION_PARENT, '100')
    run = arc.cli.new_run(settings, 'evaluation', parent=VALIDATION_PARENT,
        run_id=source.run_id + '.comparison.ARC')
    store.save_artifact(f'evaluations/{source.run_id}/evidence.json', '{}')
    cached = {'schema_version': 'arc.v1', 'task_id': run.run_id + '.frame',
        'subject': {'campaign_id': None, 'run_id': run.run_id, 'card_id': None, 'card_version': None},
        'result_status': 'blocked', 'result': None, 'evidence_requests': [],
        'capability_requests': [], 'note': 'Empty original response contains no scientific judgment.'}
    task = failed_record(store, run, key='frame', status='PAUSED_EXTERNAL', cached=cached)
    before = task.model_dump(mode='json')
    entry = prepare_comparison_retry(store, ledger, source.run_id, 'ARC', 'frame', REASON)
    audit = json.loads(store.read_artifact(entry['audit_path']))
    assert audit['superseded_cached_envelope'] == cached
    assert 'frame' not in store.get_run(run.run_id).state['comparison_envelopes']
    result = await _frozen_call(store, ComparisonRuntime(store, calls), run.run_id,
        'frame', 'discovery', 'FRAME', {'topic': 'Original frozen topic'})
    assert result.mandate.topic == 'Original frozen topic'
    assert calls[-1]['task_id'].endswith('.frame.protocol_retry1')
    assert store.get_task(task.task_id).model_dump(mode='json') == before
    with pytest.raises(StateError, match='REQUIRES_FAILED_OR_BLOCKED_RUN'):
        prepare_comparison_retry(store, ledger, source.run_id, 'ARC', 'frame', REASON)


@pytest.mark.asyncio
async def test_retry_rejects_accepted_scientific_result_and_unsettled_calls(tmp_path, monkeypatch):
    settings, store, source, calls, ledger, run, task = await setup_failed_comparison(tmp_path, monkeypatch)
    ledger.reserve(run.budget_account_id, 'pending-model', '1')
    with pytest.raises(StateError, match='HAS_UNSETTLED_CALLS'):
        prepare_comparison_retry(store, ledger, source.run_id, 'ARC', 'compose', REASON)
    ledger.mark_not_sent('pending-model')
    with pytest.raises(StateError, match='UNACCEPTED_FAILED_TASK'):
        prepare_comparison_retry(store, ledger, source.run_id, 'ARC', 'family', REASON)
    before = store.get_run(run.run_id).model_dump(mode='json')
    with pytest.raises(StateError, match='INVALID_SYSTEM_TASK_OR_REASON'):
        prepare_comparison_retry(store, ledger, source.run_id, 'ARC', 'compose', ' ')
    assert store.get_run(run.run_id).model_dump(mode='json') == before


@pytest.mark.asyncio
async def test_retry_does_not_redraw_a_needs_evidence_scientific_response(tmp_path, monkeypatch):
    settings, store, source, calls, ledger, run, task = await setup_failed_comparison(tmp_path, monkeypatch)
    state = json.loads(store.read_artifact(task.response_artifact_path))
    state['response']['message']['content'] = json.dumps({'result_status': 'needs_evidence'})
    store.save_artifact(task.response_artifact_path, json.dumps(state))
    task.status = 'PAUSED_EXTERNAL'
    store.put_task(task)
    store.update_run(run.run_id, status='PAUSED_EXTERNAL')
    with pytest.raises(StateError, match='EXTERNAL_RESULT_NOT_BLOCKED'):
        prepare_comparison_retry(store, ledger, source.run_id, 'ARC', 'compose', REASON)


@pytest.mark.parametrize('key,system,options', [('compose', 'ARC', {}),
    ('judge.seed20260908.forward', 'evaluator', {'seed': 20260908, 'include_swapped_order': False}),
    ('judge.seed20260908.swapped', 'evaluator', {'seed': 20260908, 'include_swapped_order': True})])
def test_retry_comparison_cli_routes_explicit_task_then_continues(tmp_path, monkeypatch, key, system, options):
    import arc.cli
    import arc.comparison_retry
    import arc.evaluation
    calls = []
    monkeypatch.setattr(arc.cli, 'services', lambda _: ('store', 'ledger'))
    def prepare(*args):
        calls.append(('prepare', args))
        return {'replacement_key': 'compose.protocol_retry1'}
    async def compare(settings, source_run, **kwargs):
        calls.append(('compare', source_run, kwargs))
    monkeypatch.setattr(arc.comparison_retry, 'prepare_comparison_retry', prepare)
    monkeypatch.setattr(arc.evaluation, 'run_comparison', compare)
    result = CliRunner().invoke(app, ['--data-dir', str(tmp_path), 'retry-comparison-task',
        'source-run', '--system', system, '--task-key', key, '--reason', REASON])
    assert result.exit_code == 0, result.output
    assert calls == [('prepare', ('store', 'ledger', 'source-run', system, key, REASON)),
                     ('compare', 'source-run', options)]


@pytest.mark.asyncio
async def test_explicit_evaluator_retry_preserves_anonymous_candidates_and_restricts_keys(tmp_path, monkeypatch):
    import arc.cli
    settings, store, source, calls, ledger, _, _ = await setup_failed_comparison(tmp_path, monkeypatch)
    run = arc.cli.new_run(settings, 'evaluation', parent=VALIDATION_PARENT,
        run_id=source.run_id + '.comparison.evaluator')
    original = failed_record(store, run, key='judge').model_dump(mode='json')
    for system, key in [('evaluator', 'compose'), ('ARC', 'judge'), ('direct-Pro', 'judge')]:
        with pytest.raises(StateError, match='TASK_NOT_IN_SYSTEM'):
            prepare_comparison_retry(store, ledger, source.run_id, system, key, REASON)
    entry = prepare_comparison_retry(store, ledger, source.run_id, 'evaluator', 'judge', REASON)
    candidates = [{'candidate_id': 'candidate_1', 'research_card': None},
                  {'candidate_id': 'candidate_2', 'research_card': None}]
    before = copy.deepcopy(candidates)
    result = await _frozen_call(store, ComparisonRuntime(store, calls), run.run_id,
        'judge', 'evaluator', payload={'candidates': candidates})
    assert entry['replacement_key'] == 'judge.protocol_retry1'
    assert [c.candidate_id for c in result.per_candidate_findings] == ['candidate_1', 'candidate_2']
    assert candidates == before and calls[-1]['payload']['candidates'] == before
    assert calls[-1]['tools'] == []
    assert store.get_task(run.run_id + '.judge').model_dump(mode='json') == original


@pytest.mark.asyncio
@pytest.mark.parametrize('key,options', [
    ('judge.seed20260908.forward', {'seed': 20260908, 'include_swapped_order': False}),
    ('judge.seed20260908.swapped', {'seed': 20260908, 'include_swapped_order': True}),
    ('judge.seed20260907.swapped', {'seed': 20260907, 'include_swapped_order': True}),
])
async def test_seeded_order_retry_preserves_other_judgments_and_the_presented_candidates(tmp_path, monkeypatch, key, options):
    import arc.cli
    settings, store, source, calls = environment(tmp_path, monkeypatch)
    ledger = BudgetLedger(store.db_path)
    ledger.create_account(VALIDATION_PARENT, '100')
    run = arc.cli.new_run(settings, 'evaluation', parent=VALIDATION_PARENT,
        run_id=source.run_id + '.comparison.evaluator')
    frozen_path = f'evaluations/{source.run_id}/evidence.json'
    store.save_artifact(frozen_path, '{}')
    candidates = [{'candidate_id': 'candidate_2', 'research_card': None},
        {'candidate_id': 'candidate_1', 'research_card': None}]
    runtime = ComparisonRuntime(store, calls)
    other = await _frozen_call(store, runtime, run.run_id, 'judge', 'evaluator',
        payload={'candidates': list(reversed(candidates))})
    original = failed_record(store, store.get_run(run.run_id), key=key)
    before = original.model_dump(mode='json')
    raw = store.read_artifact(original.response_artifact_path)
    old_state = copy.deepcopy(store.get_run(run.run_id).state)
    budget = ledger.summary(VALIDATION_PARENT)
    assert comparison_retry_options(key) == options
    for system in ['ARC', 'direct-Pro']:
        with pytest.raises(StateError, match='TASK_NOT_IN_SYSTEM'):
            prepare_comparison_retry(store, ledger, source.run_id, system, key, REASON)
    entry = prepare_comparison_retry(store, ledger, source.run_id, 'evaluator', key, REASON)
    assert entry['replacement_key'] == key + '.protocol_retry1'
    assert store.get_run(run.run_id).state['comparison_envelopes']['judge'] == old_state['comparison_envelopes']['judge']
    result = await _frozen_call(store, runtime, run.run_id, key, 'evaluator', payload={'candidates': candidates})
    assert [finding.candidate_id for finding in result.per_candidate_findings] == ['candidate_2', 'candidate_1']
    assert calls[-1]['task_id'] == run.run_id + '.' + entry['replacement_key']
    assert calls[-1]['payload']['candidates'] == candidates and calls[-1]['tools'] == []
    assert ledger.summary(VALIDATION_PARENT) == budget
    assert store.read_artifact(frozen_path) == '{}'
    assert store.get_task(original.task_id).model_dump(mode='json') == before
    assert store.read_artifact(original.response_artifact_path) == raw
    count = len(calls)
    assert await _frozen_call(store, runtime, run.run_id, 'judge', 'evaluator', payload={}) == other
    assert await _frozen_call(store, runtime, run.run_id, key, 'evaluator', payload={}) == result
    assert len(calls) == count


@pytest.mark.asyncio
async def test_retry_audit_serializes_value_error_diagnostic_context(tmp_path, monkeypatch):
    import arc.comparison_retry
    settings, store, source, calls, ledger, run, task = await setup_failed_comparison(tmp_path, monkeypatch)
    monkeypatch.setattr(arc.comparison_retry, 'output_validation_errors',
        lambda *_: [{'type': 'value_error', 'ctx': {'error': ValueError('invalid relation')}}])
    entry = prepare_comparison_retry(store, ledger, source.run_id, 'ARC', 'compose', REASON)
    audit = json.loads(store.read_artifact(entry['audit_path']))
    assert audit['protocol_retry']['validation_errors'] == [
        {'type': 'value_error', 'ctx': {'error': 'invalid relation'}}]


def test_reference_feedback_locates_all_bad_ids_without_guessing_claim_prefix_mapping():
    material = {'sources': [{'source_id': 'src_real'}], 'evidence': [
        {'evidence_id': 'ev_registered', 'claim_id': 'claim_same_suffix', 'source_id': 'src_real'}]}
    result = {'result': {'card_candidate': {'claims': [
        {'claim_id': 'claim_same_suffix', 'evidence_ids': ['ev_same_suffix', 'ev_registered']}],
        'closest_work_delta': {'source_ids': ['src_missing']}}}}
    raw = json.dumps(result)
    before = copy.deepcopy(material)
    errors, catalog = frozen_reference_diagnostics(raw, material)
    assert [(e['loc'], e['submitted_value']) for e in errors] == [
        (['result', 'card_candidate', 'claims', 0, 'evidence_ids', 0], 'ev_same_suffix'),
        (['result', 'card_candidate', 'closest_work_delta', 'source_ids', 0], 'src_missing')]
    assert all(e['feedback_only'] and 'replacement' not in e for e in errors)
    assert catalog == {'evidence': material['evidence'], 'source_ids': ['src_real']}
    assert json.loads(raw) == result and material == before
    from arc.runtime import reference_ids, EVIDENCE_REF_KEYS
    assert reference_ids({'errors': errors, 'catalog': catalog}, EVIDENCE_REF_KEYS) == {'ev_registered'}
    assert frozen_reference_diagnostics('not JSON', material) == ([], None)


@pytest.mark.asyncio
async def test_semantic_reference_failure_retry_receives_field_and_frozen_registry(tmp_path, monkeypatch):
    settings, store, source, calls, ledger, run, task = await setup_failed_comparison(tmp_path, monkeypatch)
    from tests.test_selection import research_draft
    from arc.schemas import ComposeResult, Envelope, Subject
    draft = research_draft()
    draft.motivation.evidence_ids = ['ev_invented_from_claim_id']
    envelope = Envelope[ComposeResult](schema_version='arc.v1', task_id=task.task_id,
        subject=Subject(run_id=run.run_id, campaign_id=run.campaign_id,
                        card_id=run.card_id, card_version=run.card_version),
        result_status='complete', result=ComposeResult(card_candidate=draft,
            composition_reason='Original scientific content.', unresolved_prerequisites=[]),
        evidence_requests=[], capability_requests=[], note=None)
    saved = json.loads(store.read_artifact(task.response_artifact_path))
    raw = envelope.model_dump_json()
    saved['response']['message']['content'] = raw
    store.save_artifact(task.response_artifact_path, json.dumps(saved))
    task.error = 'unknown_evidence_id'
    store.put_task(task)
    before = task.model_dump(mode='json')
    entry = prepare_comparison_retry(store, ledger, source.run_id, 'ARC', 'compose', REASON)
    retry = json.loads(store.read_artifact(entry['audit_path']))['protocol_retry']
    assert retry['previous_error'] == 'unknown_evidence_id'
    assert retry['validation_errors'] == [{
        'type': 'reference_not_in_frozen_material',
        'loc': ['result', 'card_candidate', 'motivation', 'evidence_ids', 0],
        'reference_kind': 'evidence', 'submitted_value': 'ev_invented_from_claim_id',
        'msg': 'The supplied frozen material does not contain this reference ID.', 'feedback_only': True}]
    assert retry['frozen_reference_catalog']['evidence'][0]['evidence_id'] == 'ev_synthetic'
    assert retry['unaccepted_response'] == raw
    assert store.get_task(task.task_id).model_dump(mode='json') == before
    assert json.loads(store.read_artifact(task.response_artifact_path)) == saved
