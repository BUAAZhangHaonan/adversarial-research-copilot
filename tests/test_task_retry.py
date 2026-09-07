"""User-triggered protocol task revisions preserve research and accounting state."""
from __future__ import annotations

import copy
import json

import pytest
from typer.testing import CliRunner

from arc.budget import BudgetLedger
from arc.cli import app
from arc.config import Settings
from arc.retrying import prepare_task_retry
from arc.schemas import Envelope, ModeratorResult, Subject, TaskRecord
from arc.store import StateError
from arc.workflows import WorkflowEngine, WorkflowPause
from tests.test_selection import research_draft, research_store
from tests.test_workflows import ScriptedRuntime

KEY = 'round1.moderator'
REASON = 'User requests a new moderator task after reviewing the structural failure.'
RAW = '{"result":{"claims":[]}}'


def failed_task(store, run_id, key=KEY):
    task_id = f'{run_id}.{key}'
    prompt = store.save_artifact(f'tests/{task_id}.prompt.json', json.dumps({'prompt_id': 'moderator.INVOKE'}))
    response = store.save_artifact(f'tests/{task_id}.failed.json', json.dumps({
        'response': {'message': {'content': RAW}},
        'repair_counts': {'tool_arguments': 1, 'output_json': 1},
        'original_tools': [{'type': 'function', 'function': {'name': 'read_record'}}],
        'tool_trace': [
            {'name': 'read_record', 'status': 'completed', 'result': {'record': 'Already read original source.'}},
            {'name': 'read_record', 'status': 'failed', 'result': {'error': 'bad arguments'}},
        ],
    }))
    record = TaskRecord(task_id=task_id, run_id=run_id, input_hash='test-input',
        prompt_hash='test-prompt', model_config_hash='test-model', status='PAUSED_PROTOCOL',
        rendered_prompt_path=prompt, response_artifact_path=response,
        error='INVALID_OUTPUT_AFTER_REPAIR')
    store.put_task(record)
    return store.get_task(task_id)


def setup_case(tmp_path, *, paused=True):
    store, _, _ = research_store(tmp_path)
    card = store.save_card(research_draft())
    ledger = BudgetLedger(tmp_path/'state.sqlite')
    ledger.create_account('parent', '100')
    ledger.create_account('stage', '25', parent_id='parent')
    ledger.reserve('stage', 'old-call', '2')
    ledger.mark_started('old-call')
    ledger.settle('old-call', '1', '1', 'usage_calculated')
    run = store.create_run('run', card_id=card.card_id, card_version=card.version,
        budget_account_id='stage', run_id='research-run')
    if paused:
        inputs = {'payload': {'card': card.model_dump(mode='json'), 'frozen_context': 'Original science'},
                  'subject': {'campaign_id': None, 'run_id': run.run_id,
                              'card_id': card.card_id, 'card_version': card.version}}
        store.update_run(run.run_id, status='PAUSED_PROTOCOL', stop_reason='INVALID_OUTPUT_AFTER_REPAIR',
                         state={'task_inputs': {KEY: inputs}})
        failed_task(store, run.run_id)
    return store, ledger, store.get_run(run.run_id), card


def snapshot(store, ledger, run, card):
    task = store.get_task(f'{run.run_id}.{KEY}')
    return {'task': task.model_dump(mode='json'), 'raw': store.read_artifact(task.response_artifact_path),
            'card': store.get_card(card.card_id, card.version).model_dump(mode='json'),
            'calls': ledger.list_calls(), 'stage': ledger.summary('stage'), 'parent': ledger.summary('parent')}


def test_prepare_preserves_failure_science_budget_and_frozen_input(tmp_path):
    store, ledger, run, card = setup_case(tmp_path)
    before = snapshot(store, ledger, run, card)
    old_inputs = copy.deepcopy(run.state['task_inputs'])
    retry = prepare_task_retry(store, ledger, run.run_id, KEY, REASON)
    assert snapshot(store, ledger, run, card) == before

    updated = store.get_run(run.run_id)
    assert updated.status == 'RUNNING' and updated.stop_reason is None
    assert updated.budget_account_id == 'stage'
    assert updated.state['task_inputs'] == old_inputs
    assert KEY not in updated.state
    assert retry['replacement_key'] == KEY + '.protocol_retry1'
    assert store.get_task(f"{run.run_id}.{retry['replacement_key']}") is None
    audit = json.loads(store.read_artifact(retry['audit_path']))
    assert audit['trigger'] == 'explicit_user_command' and audit['reason'] == REASON
    assert audit['budget_account_id'] == 'stage'
    assert audit['original_input'] == old_inputs[KEY]
    assert audit['tool_profile'] == ['read_record']
    repair = audit['protocol_retry']
    assert repair['unaccepted_response'] == RAW
    assert repair['previous_task_id'] == before['task']['task_id']
    assert repair['validation_errors']
    assert len(repair['previous_successful_tools']) == 1
    assert repair['previous_successful_tools'][0]['status'] == 'completed'
    with pytest.raises(StateError, match='PROTOCOL_PAUSE'):
        prepare_task_retry(store, ledger, run.run_id, KEY, REASON)


def accepted_anchor_failure(store, run, card, *, key=KEY, changed_anchor=True):
    """A schema-valid model result rejected before saving its proposed card."""
    source = failed_task(store, run.run_id, key)
    result = ScriptedRuntime(store).reply('moderator', 'INVOKE', {}, source.task_id)
    result['proposed_card_revision'] = card.draft.model_dump(mode='json')
    if changed_anchor:
        result['proposed_card_revision']['problem_anchor']['conditions'].append(
            'New measurement details belong in the method, not the frozen anchor.')
    envelope = Envelope[ModeratorResult](schema_version='arc.v1', task_id=source.task_id,
        subject=Subject(campaign_id=None, run_id=run.run_id,
                        card_id=card.card_id, card_version=card.version),
        result_status='complete', result=ModeratorResult.model_validate(result),
        evidence_requests=[], capability_requests=[], note=None)
    saved = json.loads(store.read_artifact(source.response_artifact_path))
    saved['response']['message']['content'] = envelope.model_dump_json()
    saved['tool_trace'][0]['result']['record'] = 'Read by ' + key
    source.response_artifact_path = store.save_artifact(
        f'tests/{source.task_id}.accepted.json', json.dumps(saved))
    source.status = 'ACCEPTED'
    source.error = None
    source.accepted_result = envelope.model_dump(mode='json')
    store.put_task(source)
    state = copy.deepcopy(store.get_run(run.run_id).state)
    state[KEY] = copy.deepcopy(result)
    if key != KEY:
        state[key] = copy.deepcopy(result)
    state[KEY + '_trace_tasks'] = [source.task_id]
    state[KEY + '_evidence_requests'] = [{'preserve_in_audit': True}]
    state['round1.proposer'] = {'already_completed': True}
    store.update_run(run.run_id, status='PAUSED_PROTOCOL',
        stop_reason='problem_anchor_changed', state=state)
    return source, result


@pytest.mark.asyncio
async def test_anchor_application_retry_keeps_accepted_history_and_executes_new_task(tmp_path):
    store, ledger, run, card = setup_case(tmp_path)
    first = prepare_task_retry(store, ledger, run.run_id, KEY, REASON)
    source, result = accepted_anchor_failure(store, run, card, key=first['replacement_key'])
    before = snapshot(store, ledger, run, card)
    source_before = source.model_dump(mode='json')
    source_raw = store.read_artifact(source.response_artifact_path)
    state_before = copy.deepcopy(store.get_run(run.run_id).state)
    retry = prepare_task_retry(store, ledger, run.run_id, KEY,
        'User requests preserving the frozen anchor and relocating measurement details.')
    assert retry['replacement_key'] == KEY + '.protocol_retry2'
    assert retry['source_task_id'] == source.task_id
    assert snapshot(store, ledger, run, card) == before
    assert store.get_task(source.task_id).model_dump(mode='json') == source_before
    assert store.read_artifact(source.response_artifact_path) == source_raw
    state = store.get_run(run.run_id).state
    assert all(k not in state for k in (KEY, KEY + '_trace_tasks', KEY + '_evidence_requests'))
    assert state[first['replacement_key']] == result
    assert state['task_inputs'] == state_before['task_inputs']
    assert state['round1.proposer'] == state_before['round1.proposer']
    audit = json.loads(store.read_artifact(retry['audit_path']))
    assert audit['application_failure']['type'] == 'problem_anchor_changed'
    assert audit['application_failure']['expected'] == card.draft.problem_anchor.model_dump(mode='json')
    assert audit['application_failure']['submitted'] == result['proposed_card_revision']['problem_anchor']
    assert audit['superseded_cached_result'] == result
    assert audit['protocol_retry']['validation_errors'] == [audit['application_failure']]
    assert json.loads(audit['protocol_retry']['unaccepted_response']) == source.accepted_result
    reads = [t['result']['record'] for t in audit['protocol_retry']['previous_successful_tools']]
    assert 'Already read original source.' in reads
    assert 'Read by ' + first['replacement_key'] in reads
    runtime = ScriptedRuntime(store)
    engine = WorkflowEngine(store, runtime, Settings())
    corrected = await engine.call(run.run_id, KEY, 'moderator', payload={'must_not_override': True})
    assert len(runtime.calls) == 1
    assert runtime.calls[0]['task_id'] == f"{run.run_id}.{retry['replacement_key']}"
    assert 'must_not_override' not in runtime.calls[0]['payload']
    assert corrected.proposed_card_revision is None
    assert store.get_run(run.run_id).state[KEY] == corrected.model_dump(mode='json')
    assert store.get_task(source.task_id).model_dump(mode='json') == source_before
    assert store.read_artifact(source.response_artifact_path) == source_raw
    assert snapshot(store, ledger, run, card) == before


@pytest.mark.parametrize('change', ['other_stop_reason', 'unchanged_anchor', 'mismatched_cache'])
def test_anchor_application_retry_rejects_unrelated_or_inconsistent_state(tmp_path, change):
    store, ledger, run, card = setup_case(tmp_path)
    source, _ = accepted_anchor_failure(store, run, card, changed_anchor=change != 'unchanged_anchor')
    if change == 'other_stop_reason':
        store.update_run(run.run_id, stop_reason='unknown_evidence_id')
    elif change == 'mismatched_cache':
        state = copy.deepcopy(store.get_run(run.run_id).state)
        state[KEY]['concise_ruling'] = 'Not the accepted source result.'
        store.update_run(run.run_id, state=state)
    before = snapshot(store, ledger, run, card)
    run_before = store.get_run(run.run_id)
    with pytest.raises(StateError):
        prepare_task_retry(store, ledger, run.run_id, KEY, REASON)
    assert snapshot(store, ledger, run, card) == before
    assert store.get_run(run.run_id) == run_before
    assert store.get_task(source.task_id) == source


@pytest.mark.parametrize('change, expected', [
    ('run_completed', 'PROTOCOL_PAUSE'), ('blank_reason', 'PROTOCOL_PAUSE'),
    ('accepted_key', 'UNACCEPTED_TASK_KEY'), ('missing_input', 'UNACCEPTED_TASK_KEY'),
    ('accepted_record', 'FAILED_TASK_RECORD'), ('pending_record', 'FAILED_TASK_RECORD'),
    ('changed_subject', 'SUBJECT_CHANGED'), ('unsettled_call', 'UNSETTLED_CALLS'),
])
def test_retry_rejects_ineligible_state_without_mutations(tmp_path, change, expected):
    store, ledger, run, card = setup_case(tmp_path)
    reason = REASON
    if change == 'run_completed':
        store.update_run(run.run_id, status='COMPLETED')
    elif change == 'blank_reason':
        reason = '  '
    elif change in ('accepted_key', 'missing_input', 'changed_subject'):
        state = copy.deepcopy(run.state)
        if change == 'accepted_key':
            state[KEY] = {'accepted': True}
        elif change == 'missing_input':
            state['task_inputs'] = {}
        else:
            state['task_inputs'][KEY]['subject']['card_version'] = 99
        store.update_run(run.run_id, state=state)
    elif change in ('accepted_record', 'pending_record'):
        task = store.get_task(f'{run.run_id}.{KEY}')
        task.status = 'ACCEPTED' if change == 'accepted_record' else 'PENDING'
        if change == 'accepted_record':
            task.accepted_result = {'result': {}}
        store.put_task(task)
    else:
        ledger.reserve('stage', 'unsettled', '1')
    before = snapshot(store, ledger, run, card)
    run_before = store.get_run(run.run_id)
    with pytest.raises(StateError, match=expected):
        prepare_task_retry(store, ledger, run.run_id, KEY, reason)
    assert snapshot(store, ledger, run, card) == before
    assert store.get_run(run.run_id) == run_before


class ModeratorFailureRuntime(ScriptedRuntime):
    async def invoke(self, **kwargs):
        if kwargs['role'] == 'moderator' and '.protocol_retry' not in kwargs['task_id']:
            self.calls.append({'role': 'moderator', 'task_id': kwargs['task_id']})
            failed_task(self.store, kwargs['subject'].run_id)
            raise WorkflowPause('PAUSED_PROTOCOL', 'INVALID_OUTPUT_AFTER_REPAIR')
        return await super().invoke(**kwargs)


@pytest.mark.asyncio
async def test_retry_completes_same_workflow_without_replaying_completed_roles(tmp_path):
    store, ledger, run, card = setup_case(tmp_path, paused=False)
    runtime = ModeratorFailureRuntime(store)
    engine = WorkflowEngine(store, runtime, Settings())
    failed = await engine.execute(run.run_id)
    assert failed.status == 'PAUSED_PROTOCOL'
    assert [c['role'] for c in runtime.calls] == ['proposer', 'skeptic', 'moderator']
    old_inputs = copy.deepcopy(failed.state['task_inputs'][KEY])
    old_results = {k: copy.deepcopy(failed.state[k]) for k in ['round1.proposer', 'round1.skeptic']}
    before = snapshot(store, ledger, failed, card)
    retry = prepare_task_retry(store, ledger, run.run_id, KEY, REASON)
    completed = await engine.execute(run.run_id)
    assert completed.status == 'COMPLETED' and completed.stop_reason == 'experiment_required'
    assert completed.card_id == card.card_id and completed.card_version == card.version
    assert snapshot(store, ledger, run, card) == before
    assert [c['role'] for c in runtime.calls] == ['proposer', 'skeptic', 'moderator', 'moderator']
    replacement = runtime.calls[-1]
    assert replacement['task_id'] == f"{run.run_id}.{retry['replacement_key']}"
    assert {k: v for k, v in replacement['payload'].items() if k != 'protocol_retry'} == old_inputs['payload']
    assert replacement['payload']['protocol_retry']['unaccepted_response'] == RAW
    assert completed.state['task_inputs'][KEY] == old_inputs
    assert all(completed.state[k] == v for k, v in old_results.items())
    assert completed.state[KEY] == completed.state[retry['replacement_key']]
    assert completed.state[KEY + '_trace_tasks'] == [f'{run.run_id}.{KEY}', replacement['task_id']]
    assert store.get_task(replacement['task_id']).status == 'ACCEPTED'
    await engine.execute(run.run_id)
    assert len(runtime.calls) == 4


@pytest.mark.asyncio
async def test_retry_uses_frozen_input_and_rejects_role_or_subject_drift(tmp_path):
    store, ledger, run, _ = setup_case(tmp_path)
    prepare_task_retry(store, ledger, run.run_id, KEY, REASON)
    runtime = ScriptedRuntime(store)
    engine = WorkflowEngine(store, runtime, Settings())
    with pytest.raises(WorkflowPause, match='task_retry_role_changed'):
        await engine.call(run.run_id, KEY, 'skeptic', payload={'changed': True})
    card2 = store.save_card(research_draft(), card_id=run.card_id, parent_version=1)
    store.update_run(run.run_id, card_version=card2.version)
    with pytest.raises(WorkflowPause, match='task_retry_subject_changed'):
        await engine.call(run.run_id, KEY, 'moderator', payload={'changed': True})
    assert runtime.calls == []


def test_cli_requires_explicit_reason_and_dispatches_same_run(tmp_path, monkeypatch):
    store, ledger, run, card = setup_case(tmp_path)
    before = snapshot(store, ledger, run, card)
    dispatched = []
    monkeypatch.setattr('arc.cli.services', lambda settings: (store, ledger))
    async def local_execute(settings, run_id):
        dispatched.append(run_id)
        assert store.get_run(run_id).state['task_retries'][KEY]
        assert snapshot(store, ledger, run, card) == before
    monkeypatch.setattr('arc.cli.execute', local_execute)
    args = ['retry-task', run.run_id, '--task-key', KEY]
    missing = CliRunner().invoke(app, args)
    assert missing.exit_code != 0 and dispatched == []
    assert store.get_run(run.run_id).status == 'PAUSED_PROTOCOL'
    result = CliRunner().invoke(app, [*args, '--reason', REASON])
    assert result.exit_code == 0, result.output + repr(result.exception)
    assert dispatched == [run.run_id]
    assert json.loads(result.output)['replacement_key'] == KEY + '.protocol_retry1'

@pytest.mark.asyncio
async def test_second_task_version_requires_new_explicit_request_and_keeps_failure_chain(tmp_path):
    store, ledger, run, card = setup_case(tmp_path)
    first = prepare_task_retry(store, ledger, run.run_id, KEY, REASON)
    old_failure = store.get_task(f'{run.run_id}.{KEY}').model_dump(mode='json')
    failed_revision = failed_task(store, run.run_id, first['replacement_key'])
    store.update_run(run.run_id, status='PAUSED_PROTOCOL', stop_reason='INVALID_OUTPUT_AFTER_REPAIR')
    before = snapshot(store, ledger, run, card)
    second = prepare_task_retry(store, ledger, run.run_id, KEY, REASON + ' Reviewed the new failure.')
    assert second['replacement_key'] == KEY + '.protocol_retry2'
    assert second['source_task_id'] == failed_revision.task_id
    runtime = ScriptedRuntime(store)
    engine = WorkflowEngine(store, runtime, Settings())
    await engine.call(run.run_id, KEY, 'moderator', payload={'new_unfrozen_input': 'Must not replace original'})
    assert len(runtime.calls) == 1
    assert 'new_unfrozen_input' not in runtime.calls[0]['payload']
    assert runtime.calls[0]['payload']['frozen_context'] == 'Original science'
    assert runtime.calls[0]['payload']['protocol_retry']['previous_task_id'] == failed_revision.task_id
    assert engine.trace_tasks(run.run_id, KEY) == [f'{run.run_id}.{KEY}', failed_revision.task_id,
        f"{run.run_id}.{second['replacement_key']}"]
    assert store.get_task(f'{run.run_id}.{KEY}').model_dump(mode='json') == old_failure
    assert store.get_task(failed_revision.task_id) == failed_revision
    assert snapshot(store, ledger, run, card) == before
