"""Frozen comparison retries change only an explicitly failed physical task."""
from __future__ import annotations

import copy
import json

import pytest
from typer.testing import CliRunner

from arc.budget import BudgetLedger
from arc.cli import app
from arc.comparison_retry import prepare_comparison_retry
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
        'prompt_id': {'frame': 'discovery.FRAME', 'compose': 'discovery.COMPOSE',
                      'judge': 'evaluator.INVOKE'}[key]}))
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


def test_retry_comparison_cli_routes_explicit_task_then_continues(tmp_path, monkeypatch):
    import arc.cli
    import arc.comparison_retry
    import arc.evaluation
    calls = []
    monkeypatch.setattr(arc.cli, 'services', lambda _: ('store', 'ledger'))
    def prepare(*args):
        calls.append(('prepare', args))
        return {'replacement_key': 'compose.protocol_retry1'}
    async def compare(settings, source_run):
        calls.append(('compare', source_run))
    monkeypatch.setattr(arc.comparison_retry, 'prepare_comparison_retry', prepare)
    monkeypatch.setattr(arc.evaluation, 'run_comparison', compare)
    result = CliRunner().invoke(app, ['--data-dir', str(tmp_path), 'retry-comparison-task',
        'source-run', '--system', 'ARC', '--task-key', 'compose', '--reason', REASON])
    assert result.exit_code == 0, result.output
    assert calls == [('prepare', ('store', 'ledger', 'source-run', 'ARC', 'compose', REASON)),
                     ('compare', 'source-run')]


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
async def test_retry_audit_serializes_value_error_diagnostic_context(tmp_path, monkeypatch):
    import arc.comparison_retry
    settings, store, source, calls, ledger, run, task = await setup_failed_comparison(tmp_path, monkeypatch)
    monkeypatch.setattr(arc.comparison_retry, 'output_validation_errors',
        lambda *_: [{'type': 'value_error', 'ctx': {'error': ValueError('invalid relation')}}])
    entry = prepare_comparison_retry(store, ledger, source.run_id, 'ARC', 'compose', REASON)
    audit = json.loads(store.read_artifact(entry['audit_path']))
    assert audit['protocol_retry']['validation_errors'] == [
        {'type': 'value_error', 'ctx': {'error': 'invalid relation'}}]
