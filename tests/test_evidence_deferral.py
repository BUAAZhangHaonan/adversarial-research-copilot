"""Explicit evidence deferral preserves history and requires a new bounded judgment."""
import copy
import json

import pytest

from arc.retrying import prepare_task_retry, validate_deferred_evidence
from arc.discovery_models import CandidateCheck
from arc.runtime import Runtime
from arc.schemas import Envelope, TaskRecord
from arc.store import StateError
from arc.workflows import WorkflowEngine
from tests.test_discovery_workflow import fixture, checked, ScriptedRuntime

KEY = 'idea5.check'


def paused_case(tmp_path, monkeypatch, task='CHECK', decision='lead'):
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch, draws=5)
    result = checked(seed, brief['source_notes'][0])
    result['note']['decision'] = decision
    result['note']['limits'] = ['The critical near-neighbor full text could not be accessed.']
    subject = dict(run_id=run.run_id, campaign_id=run.campaign_id, card_id=None, card_version=None)
    payload = dict(draw_id='idea5', seed=seed, field_brief=brief)
    request = dict(request_local_id='missing-pdf', claim_id=None, issue_id=None, draw_id='idea5',
        question='Does the unavailable full text cover the central contribution?',
        target_source_ids=seed['source_ids'], queries=[], purpose='Check the central difference.',
        decision_if_supported='Drop the duplicate.', decision_if_contradicted='Keep the gap unresolved.')
    envelope = dict(schema_version='arc.v1', task_id=f'{run.run_id}.{KEY}', subject=subject,
        result_status='needs_evidence', result=result, evidence_requests=[request],
        capability_requests=[], note='Full text access is unavailable; only a lead is justified.')
    prompt_path = store.save_artifact('tests/deferred.prompt.json', json.dumps({'prompt_id': f'scout.{task}'}))
    response_path = store.save_artifact('tests/deferred.response.json', json.dumps({
        'response': {'message': {'content': json.dumps(envelope)}},
        'original_tools': [{'type': 'function', 'function': {'name': 'read_record'}}],
        'tool_trace': [{'name': 'read_record', 'status': 'completed',
                        'result': {'source_id': seed['source_ids'][0], 'content': 'Already read abstract.'}}]}))
    source = TaskRecord(task_id=envelope['task_id'], run_id=run.run_id, input_hash='test-input',
        prompt_hash='test-prompt', model_config_hash='test-model', status='PAUSED_EXTERNAL',
        rendered_prompt_path=prompt_path, response_artifact_path=response_path, error='needs_evidence')
    store.put_task(source)
    state = {**run.state, 'field_brief': brief, 'task_inputs': {KEY: {'payload': payload, 'subject': subject}},
        'pending_task': KEY, 'pending_evidence_requests': [request], 'pending_capability_requests': []}
    store.update_run(run.run_id, status='PAUSED_EXTERNAL', stop_reason='critical_source_unavailable', state=state)
    return settings, store, ledger, store.get_run(run.run_id), source, envelope


@pytest.mark.parametrize('task', ['CHECK', 'DEVELOP', 'PRESSURE'])
def test_deferral_creates_new_task_audit_without_accepting_draft_or_changing_cost(tmp_path, monkeypatch, task):
    settings, store, ledger, run, source, envelope = paused_case(tmp_path, monkeypatch, task=task)
    before = (source.model_dump(mode='json'), store.read_artifact(source.response_artifact_path),
              ledger.list_calls(), copy.deepcopy(run.state))
    retry = prepare_task_retry(store, ledger, run.run_id, KEY, 'User defers inaccessible full text.', defer_evidence=True)
    updated = store.get_run(run.run_id)
    audit = json.loads(store.read_artifact(retry['audit_path']))
    assert retry['replacement_key'] == KEY + '.protocol_retry1'
    assert updated.status == 'RUNNING' and KEY not in updated.state
    assert store.get_task(source.task_id).model_dump(mode='json') == before[0]
    assert store.read_artifact(source.response_artifact_path) == before[1]
    assert ledger.list_calls() == before[2]
    assert updated.state['task_inputs'] == before[3]['task_inputs']
    assert updated.state['pending_evidence_requests'] == envelope['evidence_requests']
    assert store.get_task(f"{run.run_id}.{retry['replacement_key']}") is None
    assert audit['retry_kind'] == 'defer_evidence'
    assert audit['protocol_retry']['deferred_evidence']['evidence_requests'] == envelope['evidence_requests']
    assert audit['protocol_retry']['previous_successful_tools'][0]['result']['content'] == 'Already read abstract.'


@pytest.mark.parametrize('case', ['ordinary_retry', 'discuss', 'wrong_task', 'wrong_pause', 'wrong_pending', 'unsettled', 'malformed'])
def test_deferral_rejects_ineligible_or_unknown_state_without_mutation(tmp_path, monkeypatch, case):
    _, store, ledger, run, source, envelope = paused_case(tmp_path, monkeypatch,
        task='SURVEY' if case == 'wrong_task' else 'CHECK', decision='discuss' if case == 'discuss' else 'lead')
    if case == 'wrong_pause':
        store.update_run(run.run_id, stop_reason='SOURCE_READ_NO_PROGRESS')
    if case == 'wrong_pending':
        store.update_run(run.run_id, state={**run.state, 'pending_task': 'idea4.check'})
    if case == 'unsettled':
        ledger.reserve(run.budget_account_id, 'unknown-call', '1')
        ledger.mark_started('unknown-call')
    if case == 'malformed':
        store.save_artifact(source.response_artifact_path, json.dumps({'response': {'message': {'content': '{}'}}}))
    before = store.get_run(run.run_id).model_dump(mode='json')
    with pytest.raises(StateError):
        prepare_task_retry(store, ledger, run.run_id, KEY, 'Explicit deferral.', defer_evidence=case != 'ordinary_retry')
    assert store.get_run(run.run_id).model_dump(mode='json') == before


@pytest.mark.parametrize('decision,limits,allowed', [('lead', ['The nearest full text remains unread.'], True),
    ('drop', ['Coverage remains unverified; drop on a separate weakness.'], True),
    ('discuss', ['Still unread.'], False), ('lead', [], False), ('lead', ['   '], False)])
def test_runtime_enforces_limited_decision_without_literal_copy_requirements(tmp_path, monkeypatch, decision, limits, allowed):
    _, store, ledger, run, _, raw = paused_case(tmp_path, monkeypatch)
    retry = prepare_task_retry(store, ledger, run.run_id, KEY, 'Explicit deferral.', defer_evidence=True)
    audit = json.loads(store.read_artifact(retry['audit_path']))
    payload = {**audit['original_input']['payload'], 'protocol_retry': audit['protocol_retry']}
    raw['result_status'] = 'complete'
    raw['result']['note']['decision'] = decision
    raw['result']['note']['limits'] = limits
    raw['evidence_requests'] = []  # They remain unresolved in audit; do not force another pause.
    envelope = Envelope[CandidateCheck].model_validate(raw)
    if allowed:
        validate_deferred_evidence(envelope, payload)
    else:
        with pytest.raises(StateError, match='EVIDENCE_DEFERRAL'):
            # Exercise the actual runtime admission hook before other contracts.
            object.__new__(Runtime)._validate_output_contracts(envelope, payload, {})


@pytest.mark.asyncio
async def test_workflow_continues_only_after_replacement_completes(tmp_path, monkeypatch):
    settings, store, ledger, run, source, raw = paused_case(tmp_path, monkeypatch)
    retry = prepare_task_retry(store, ledger, run.run_id, KEY, 'Explicit deferral.', defer_evidence=True)
    key = retry['replacement_key']
    runtime = ScriptedRuntime({key: raw['result']})
    runtime.before.add(key)
    engine = WorkflowEngine(store, runtime, settings)
    with pytest.raises(InterruptedError):
        await engine.call(run.run_id, KEY, 'scout', 'CHECK')
    assert KEY not in store.get_run(run.run_id).state
    result = await engine.call(run.run_id, KEY, 'scout', 'CHECK')
    assert result.note.decision == 'lead'
    assert store.get_run(run.run_id).state[KEY] == CandidateCheck.model_validate(raw['result']).model_dump(mode='json')
    assert runtime.calls == [(key, 'scout', 'CHECK')]
    assert runtime.payloads[key]['protocol_retry']['deferred_evidence']['allowed_decisions'] == ['lead', 'drop']
    assert store.get_task(source.task_id).accepted_result is None
    assert store.get_run(run.run_id).state['pending_evidence_requests'] == raw['evidence_requests']


def test_protocol_correction_keeps_deferral_bound(tmp_path, monkeypatch):
    _, store, ledger, run, source, raw = paused_case(tmp_path, monkeypatch)
    first = prepare_task_retry(store, ledger, run.run_id, KEY, 'Explicit deferral.', defer_evidence=True)
    failed_key = first['replacement_key']
    failed = source.model_copy(update={'task_id': f'{run.run_id}.{failed_key}', 'status': 'PAUSED_PROTOCOL',
        'response_artifact_path': 'tests/deferral-correction.json', 'error': 'INVALID_OUTPUT_AFTER_REPAIR'})
    store.save_artifact(failed.response_artifact_path, json.dumps({'response': {'message': {'content': '{}'}}}))
    store.put_task(failed)
    current = store.get_run(run.run_id)
    store.update_run(run.run_id, status='PAUSED_PROTOCOL', stop_reason=failed.error,
        state={**current.state, 'task_inputs': {**current.state['task_inputs'],
            failed_key: current.state['task_inputs'][KEY]}})
    second = prepare_task_retry(store, ledger, run.run_id, KEY, 'Correct the failed limited draft.')
    audit = json.loads(store.read_artifact(second['audit_path']))
    assert audit['protocol_retry']['deferred_evidence']['allowed_decisions'] == ['lead', 'drop']


def test_cli_passes_explicit_deferral_option(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from arc.cli import app
    settings, store, ledger, run, _, _ = paused_case(tmp_path, monkeypatch)
    seen = []
    async def execute(actual_settings, run_id):
        seen.append(run_id)
    monkeypatch.setattr('arc.cli.execute', execute)
    monkeypatch.setattr('arc.cli.services', lambda _: (store, ledger))
    result = CliRunner().invoke(app, ['retry-task', run.run_id, '--task-key', KEY,
        '--reason', 'Continue a bounded lead.', '--defer-evidence'], obj=settings)
    assert result.exit_code == 0, result.output
    assert seen == [run.run_id]
    retry = json.loads(result.output)
    assert json.loads(store.read_artifact(retry['audit_path']))['retry_kind'] == 'defer_evidence'
