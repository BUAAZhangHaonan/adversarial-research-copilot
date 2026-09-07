"""Retry only the pending empirical ruling after its card was already saved."""
import copy
import json

import pytest

from arc.budget import BudgetLedger
from arc.config import Settings
from arc.retrying import prepare_task_retry
from arc.schemas import Claim, Envelope, ModeratorResult, Subject, TaskRecord
from arc.store import StateError, claim_fingerprint
from arc.workflows import WorkflowEngine, WorkflowPause
from tests.test_selection import research_draft, research_store
from tests.test_workflows import ScriptedRuntime

KEY = 'round1.moderator.evidence_reassessment'
ERROR = 'empirical_resolution_requires_verified_claim_evidence'


def case(tmp_path, basis_case=None):
    store, _, old_evidence = research_store(tmp_path)
    draft = research_draft()
    claim = Claim(claim_id='claim_observation', version=2, text=old_evidence.claim,
        conditions=old_evidence.conditions, kind='empirical', evidence_ids=[])
    draft.claims = [claim]
    card1 = store.save_card(draft)
    ledger = BudgetLedger(tmp_path / 'state.sqlite')
    ledger.create_account('parent', '100')
    ledger.create_account('stage', '25', parent_id='parent')
    run = store.create_run('run', card_id=card1.card_id, card_version=1,
        budget_account_id='stage', run_id='run_empirical')
    good = store.register_evidence(old_evidence.model_copy(update={
        'evidence_id': 'ev_current', 'claim_version': 2, 'relation': 'supports',
        'run_id': run.run_id, 'target_claim_fingerprint': claim_fingerprint(claim)}))
    revised = draft.model_copy(deep=True)
    revised.method.simplest_path = 'The already saved measurement clarification.'
    card2 = store.save_card(revised, card_id=card1.card_id, parent_version=1,
        creation_key=run.run_id + '.round1.evidence_reassessment.revision')
    result = ScriptedRuntime(store).reply('moderator', 'INVOKE', {}, '')
    result['proposed_card_revision'] = revised.model_dump(mode='json')
    result['updated_issues'] = [{'issue_id': 'issue_empirical', 'claim_id': claim.claim_id,
        'claim_version': 2, 'content': 'Does the original observation support this claim?',
        'status': 'resolved', 'evidence_ids': [old_evidence.evidence_id],
        'resolution_criterion': 'Current verified original evidence.', 'change_this_round': 'A new reading.',
        'next_action': 'STOP', 'claim_kind': 'empirical'}]
    result['issue_transitions'] = [{'issue_id': 'issue_empirical', 'from_status': None,
        'to_status': 'resolved', 'change_this_round': 'A new reading.',
        'basis_evidence_ids': [old_evidence.evidence_id], 'basis_argument': None,
        'resolution_reason': 'The cited reading should settle this observation.'}]
    if basis_case:
        result['issue_transitions'][0]['basis_evidence_ids'] = [good.evidence_id] if basis_case == 'already_valid_evidence' else []
    task_id = run.run_id + '.' + KEY
    subject = Subject(campaign_id=None, run_id=run.run_id, card_id=card1.card_id, card_version=1)
    envelope = Envelope[ModeratorResult](schema_version='arc.v1', task_id=task_id,
        subject=subject, result_status='complete', result=ModeratorResult.model_validate(result),
        evidence_requests=[], capability_requests=[], note=None)
    prompt = store.save_artifact('tests/empirical.prompt.json', json.dumps({'prompt_id': 'moderator.INVOKE'}))
    raw = store.save_artifact('tests/empirical.raw.json', json.dumps({
        'response': {'message': {'content': envelope.model_dump_json()}},
        'original_tools': [{'function': {'name': 'read_record'}}], 'tool_trace': []}))
    task = TaskRecord(task_id=task_id, run_id=run.run_id, input_hash='frozen', prompt_hash='frozen',
        model_config_hash='frozen', status='ACCEPTED', rendered_prompt_path=prompt,
        response_artifact_path=raw, accepted_result=envelope.model_dump(mode='json'))
    store.put_task(task)
    state = {'task_inputs': {KEY: {'subject': subject.model_dump(mode='json'),
        'payload': {'card': card1.model_dump(mode='json'), 'original_science': 'Preserve original rationale.'}}},
        KEY: envelope.result.model_dump(mode='json'), 'evidence_ids': [good.evidence_id],
        'round1.proposer': {'completed': True}, 'round1.skeptic': {'completed': True},
        'round1.moderator': {'completed': True}}
    store.update_run(run.run_id, card_version=2, status='PAUSED_PROTOCOL', stop_reason=ERROR, state=state)
    if not basis_case:
        with pytest.raises(StateError, match=ERROR):
            store.apply_issues(run.run_id, envelope.result.updated_issues, envelope.result.issue_transitions)
    return store, ledger, store.get_run(run.run_id), task, card1, card2, good


def preserved(store, ledger, run, task):
    return {'task': store.get_task(task.task_id), 'raw': store.read_artifact(task.response_artifact_path),
        'cards': store.list_cards(run_id=run.run_id), 'issues': store.get_issues(run.run_id),
        'stage': ledger.summary('stage'), 'parent': ledger.summary('parent'), 'calls': ledger.list_calls()}


@pytest.mark.asyncio
async def test_empirical_retry_uses_current_card_and_evidence_without_replaying_prior_roles(tmp_path):
    store, ledger, run, task, card1, card2, good = case(tmp_path)
    before = preserved(store, ledger, run, task)
    old_inputs = copy.deepcopy(run.state['task_inputs'])
    retry = prepare_task_retry(store, ledger, run.run_id, KEY, 'User requests correcting the stale resolution citation.')
    assert preserved(store, ledger, run, task) == before
    audit = json.loads(store.read_artifact(retry['audit_path']))
    assert audit['application_failure']['type'] == ERROR
    assert audit['application_failure']['diagnostics'][0]['issue_id'] == 'issue_empirical'
    assert audit['previous_input'] == old_inputs[KEY]
    assert audit['original_input']['subject']['card_version'] == 2
    assert audit['original_input']['payload']['card'] == card2.model_dump(mode='json')
    assert good.evidence_id in [e['evidence_id'] for e in audit['original_input']['payload']['evidence']]
    assert store.get_run(run.run_id).state['task_inputs'] == old_inputs

    class Corrected(ScriptedRuntime):
        def reply(self, role, task_name, payload, task_id):
            assert role == 'moderator' and task_id.endswith('.protocol_retry1')
            assert payload['card']['version'] == 2
            result = copy.deepcopy(task.accepted_result['result'])
            result['proposed_card_revision'] = None
            result['updated_issues'][0]['evidence_ids'] = [good.evidence_id]
            result['issue_transitions'][0]['basis_evidence_ids'] = [good.evidence_id]
            return result

    runtime = Corrected(store)
    engine = WorkflowEngine(store, runtime, Settings())
    completed = await engine.execute(run.run_id)
    assert completed.status == 'COMPLETED' and completed.stop_reason == 'experiment_required'
    assert len(runtime.calls) == 1
    assert completed.card_version == 2
    assert store.get_card(card1.card_id, 1) == card1 and store.get_card(card2.card_id, 2) == card2
    assert store.get_task(task.task_id) == before['task']
    assert store.read_artifact(task.response_artifact_path) == before['raw']
    assert store.get_issues(run.run_id)[0].status == 'resolved'
    assert ledger.summary('stage') == before['stage'] and ledger.list_calls() == before['calls']
    await engine.execute(run.run_id)
    assert len(runtime.calls) == 1 and store.get_run(run.run_id).card_version == 2


@pytest.mark.parametrize('change', ['cache_mismatch', 'already_applied_round', 'different_card',
    'already_valid_evidence', 'different_issue_failure'])
def test_empirical_retry_rejects_unrelated_or_nonreproducing_application_failure(tmp_path, change):
    store, ledger, run, task, _, card2, good = case(tmp_path,
        basis_case=change if change in {'already_valid_evidence', 'different_issue_failure'} else None)
    state = copy.deepcopy(run.state)
    if change == 'cache_mismatch':
        state[KEY]['concise_ruling'] = 'An unrelated cache.'
    elif change == 'already_applied_round':
        state['rounds_completed'] = 1
    elif change == 'different_card':
        card3 = store.save_card(card2.draft, card_id=card2.card_id, parent_version=2)
        store.update_run(run.run_id, card_version=card3.version)
    store.update_run(run.run_id, state=state)
    before = preserved(store, ledger, run, task)
    run_before = store.get_run(run.run_id)
    with pytest.raises(StateError):
        prepare_task_retry(store, ledger, run.run_id, KEY, 'Explicit review does not waive eligibility.')
    assert preserved(store, ledger, run, task) == before
    assert store.get_run(run.run_id) == run_before


@pytest.mark.asyncio
async def test_empirical_issue_correction_cannot_modify_the_saved_research_card(tmp_path):
    store, ledger, run, task, _, card2, _ = case(tmp_path)
    prepare_task_retry(store, ledger, run.run_id, KEY, 'Correct the issue basis only.')
    class Unscoped(ScriptedRuntime):
        def reply(self, role, task_name, payload, task_id):
            return copy.deepcopy(task.accepted_result['result'])
    runtime = Unscoped(store)
    result = await WorkflowEngine(store, runtime, Settings()).execute(run.run_id)
    assert result.status == 'PAUSED_PROTOCOL'
    assert result.stop_reason == 'issue_application_retry_must_preserve_saved_card'
    assert result.card_version == 2 and store.get_card(card2.card_id, 2) == card2
    assert store.get_issues(run.run_id) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('first_failure', ['invalid_json', 'stale_basis'])
async def test_new_explicit_task_version_can_correct_a_failed_application_retry(tmp_path, first_failure):
    from tests.test_task_retry import failed_task
    store, ledger, run, original_task, _, card2, good = case(tmp_path)
    first = prepare_task_retry(store, ledger, run.run_id, KEY, 'First explicit issue correction.')

    class RevisionRuntime(ScriptedRuntime):
        async def invoke(self, **kw):
            if kw['task_id'].endswith('.protocol_retry1') and first_failure == 'invalid_json':
                self.calls.append({'task_id': kw['task_id']})
                failed_task(store, run.run_id, first['replacement_key'])
                raise WorkflowPause('PAUSED_PROTOCOL', 'INVALID_OUTPUT_AFTER_REPAIR')
            result = await super().invoke(**kw)
            saved = store.get_task(kw['task_id'])
            saved.rendered_prompt_path = store.save_artifact(f"tests/{saved.task_id}.prompt.json",
                json.dumps({'prompt_id': 'moderator.INVOKE'}))
            saved.response_artifact_path = store.save_artifact(f"tests/{saved.task_id}.state.json",
                json.dumps({'response': {'message': {'content': result.model_dump_json()}},
                    'original_tools': [{'function': {'name': 'read_record'}}], 'tool_trace': []}))
            store.put_task(saved)
            return result

        def reply(self, role, task_name, payload, task_id):
            assert role == 'moderator' and payload['card']['version'] == 2
            result = copy.deepcopy(original_task.accepted_result['result'])
            result['proposed_card_revision'] = None
            if task_id.endswith('.protocol_retry2'):
                result['updated_issues'][0]['evidence_ids'] = [good.evidence_id]
                result['issue_transitions'][0]['basis_evidence_ids'] = [good.evidence_id]
            return result

    runtime = RevisionRuntime(store)
    engine = WorkflowEngine(store, runtime, Settings())
    failed = await engine.execute(run.run_id)
    assert failed.status == 'PAUSED_PROTOCOL'
    assert failed.stop_reason == ('INVALID_OUTPUT_AFTER_REPAIR' if first_failure == 'invalid_json' else ERROR)
    assert len(runtime.calls) == 1 and failed.card_version == 2
    failed_task_record = store.get_task(run.run_id + '.' + first['replacement_key'])
    failed_raw = store.read_artifact(failed_task_record.response_artifact_path)
    old_inputs = copy.deepcopy(failed.state['task_inputs'])
    before = preserved(store, ledger, run, original_task)
    second = prepare_task_retry(store, ledger, run.run_id, KEY, 'User explicitly reviews and requests a second correction task.')
    assert second['replacement_key'].endswith('.protocol_retry2')
    audit = json.loads(store.read_artifact(second['audit_path']))
    assert audit['original_input']['subject']['card_version'] == 2
    assert audit['previous_input'] == old_inputs[first['replacement_key']]
    if first_failure == 'invalid_json':
        assert audit['protocol_retry']['validation_errors'][-1]['type'] == 'empirical_application_correction_scope'
        assert audit['protocol_retry']['validation_errors'][-1]['proposed_card_revision'] is None
    assert store.get_run(run.run_id).state['task_inputs'] == old_inputs
    assert preserved(store, ledger, run, original_task) == before
    assert store.get_task(failed_task_record.task_id) == failed_task_record
    completed = await engine.execute(run.run_id)
    assert completed.status == 'COMPLETED' and completed.card_version == 2
    assert completed.stop_reason == 'experiment_required'
    assert len(runtime.calls) == 2
    assert store.get_card(card2.card_id, 2) == card2
    assert store.get_task(failed_task_record.task_id) == failed_task_record
    assert store.read_artifact(failed_task_record.response_artifact_path) == failed_raw
    assert ledger.summary('stage') == before['stage'] and ledger.list_calls() == before['calls']
    assert store.get_run(run.run_id).state['task_inputs'][KEY] == old_inputs[KEY]
    await engine.execute(run.run_id)
    assert len(runtime.calls) == 2
