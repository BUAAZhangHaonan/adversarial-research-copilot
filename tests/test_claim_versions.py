"""Mechanical claim versions preserve scientific output and old evidence."""
from collections import Counter
from copy import deepcopy
import json

import pytest

from arc.config import Settings
from arc.schemas import Claim, DeveloperResult, ModeratorResult
from arc.store import Store, StateError
from arc.validation import derive_claim_versions, validate_revision, ProtocolViolation
from arc.workflows import WorkflowEngine
from .test_contracts import card_payload
from .test_claim_targets import claim, revision_payload
from .test_selection import research_store, research_draft
from .test_workflows import ScriptedRuntime


def case(tmp_path, *, version=1):
    store = Store(tmp_path / 'versions.sqlite')
    draft = card_payload()
    draft['claims'] = [claim('C1', version)]
    original = store.save_card(draft)
    proposed = deepcopy(draft)
    proposed['claims'][0]['conditions'].append('Only the explicitly controlled subset.')
    result = DeveloperResult.model_validate(revision_payload(draft, proposed))
    return store, original, result


@pytest.mark.parametrize('field,value', [
    ('text', 'The effect is a bounded hypothesis, not an observed result.'),
    ('conditions', ['Only the explicitly controlled subset.']),
    ('kind', 'logical'),
])
def test_changed_scientific_field_gets_one_version_without_changing_original(tmp_path, field, value):
    store, original, result = case(tmp_path)
    result.proposed_revision.claims[0] = original.draft.claims[0].model_copy(deep=True)
    setattr(result.proposed_revision.claims[0], field, value)
    raw = result.model_dump(mode='json')
    derived, changes, references = derive_claim_versions(original, result)
    assert changes == [{'claim_id': 'C1', 'original_version': 1, 'submitted_version': 1,
                        'effective_version': 2, 'changed_fields': [field]}]
    expected = deepcopy(raw)
    expected['proposed_revision']['claims'][0]['version'] = 2
    expected['evidence_review'][0]['claim_version'] = 2
    assert derived.model_dump(mode='json') == expected
    assert result.model_dump(mode='json') == raw
    assert store.get_card(original.card_id, 1) == original
    assert references[0]['path'] == 'evidence_review.0.claim_version'
    validate_revision(store, original, derived)


@pytest.mark.parametrize('proposed_version', [2, 4])
def test_already_incremented_version_is_preserved_exactly(tmp_path, proposed_version):
    store, original, result = case(tmp_path)
    result.proposed_revision.claims[0].version = proposed_version
    result.evidence_review[0].claim_version = proposed_version
    derived, changes, references = derive_claim_versions(original, result)
    assert derived == result and changes == references == []
    validate_revision(store, original, derived)


def test_version_regression_and_wrong_review_stay_errors(tmp_path):
    store, original, result = case(tmp_path, version=2)
    result.proposed_revision.claims[0].version = 1
    result.evidence_review[0].claim_version = 1
    derived, changes, _ = derive_claim_versions(original, result)
    assert not changes and derived.proposed_revision.claims[0].version == 1
    with pytest.raises(StateError, match='claim_version_cannot_regress'):
        validate_revision(store, original, derived)
    result.proposed_revision.claims[0].version = 2
    result.evidence_review[0].claim_version = 9
    derived, _, _ = derive_claim_versions(original, result)
    assert derived.evidence_review[0].claim_version == 9
    with pytest.raises(ProtocolViolation, match='CLAIM_REVIEW_VERSION'):
        validate_revision(store, original, derived)


def test_derivation_does_not_fill_affected_claims_or_reviews(tmp_path):
    store, original, result = case(tmp_path)
    result.affected_claims = []
    derived, _, _ = derive_claim_versions(original, result)
    assert derived.affected_claims == []
    with pytest.raises(ProtocolViolation, match='AFFECTED_CLAIMS_COVERAGE'):
        validate_revision(store, original, derived)
    result.affected_claims = ['C1']
    result.evidence_review = []
    derived, _, _ = derive_claim_versions(original, result)
    with pytest.raises(ProtocolViolation, match='CLAIM_REVIEW_COVERAGE'):
        validate_revision(store, original, derived)


def test_evidence_only_change_does_not_increment_claim(tmp_path):
    _, original, result = case(tmp_path)
    result.proposed_revision.claims[0] = original.draft.claims[0].model_copy(deep=True)
    result.proposed_revision.claims[0].evidence_ids = ['explicit_new_reference']
    derived, changes, references = derive_claim_versions(original, result)
    assert derived == result and not changes and not references
    assert derived.proposed_revision.claims[0].version == original.draft.claims[0].version


def issue(identifier, *, version=1):
    return {'issue_id': identifier, 'claim_id': 'C1', 'claim_version': version,
            'content': 'The narrowed condition remains untested.', 'status': 'needs_experiment',
            'evidence_ids': [], 'resolution_criterion': 'A controlled experiment.',
            'change_this_round': 'Explicitly limited the question.', 'next_action': 'HANDOFF_EXPERIMENT',
            'claim_kind': 'hypothesis'}


def moderator(proposed, issues):
    return ModeratorResult.model_validate({
        'assessment': 'NEEDS_EVIDENCE', 'next_action': 'HANDOFF_EXPERIMENT',
        'stop_reason': 'An experiment is required.', 'concise_ruling': 'The condition is narrower.',
        'updated_issues': issues,
        'issue_transitions': [{'issue_id': i['issue_id'], 'from_status': None,
            'to_status': i['status'], 'change_this_round': i['change_this_round'],
            'basis_evidence_ids': [], 'basis_argument': None, 'resolution_reason': None} for i in issues],
        'decisive_evidence_ids': [], 'proposed_card_revision': proposed,
        'external_test_requirements': ['Execute the controlled experiment.'], 'direction_change': None})


def test_only_explicit_new_moderator_issue_moves_existing_target_is_preserved(tmp_path):
    _, original, development = case(tmp_path)
    old, new = issue('existing'), issue('new')
    result = moderator(development.proposed_revision, [old, new])
    before = result.model_dump(mode='json')
    derived, _, references = derive_claim_versions(original, result, prior_issues=[old], new_issue_contract=True)
    assert [(i.issue_id, i.claim_version) for i in derived.updated_issues] == [('existing', 1), ('new', 2)]
    assert references == [{'path': 'updated_issues.1.claim_version', 'claim_id': 'C1',
                           'submitted_version': 1, 'effective_version': 2}]
    expected = deepcopy(before)
    expected['proposed_card_revision']['claims'][0]['version'] = 2
    expected['updated_issues'][1]['claim_version'] = 2
    assert derived.model_dump(mode='json') == expected and result.model_dump(mode='json') == before


def test_old_moderator_without_explicit_target_contract_cannot_guess(tmp_path):
    _, original, development = case(tmp_path)
    result = moderator(development.proposed_revision, [issue('new')])
    with pytest.raises(ProtocolViolation, match='CLAIM_VERSION_ISSUE_TARGET_AMBIGUOUS'):
        derive_claim_versions(original, result)


def test_new_issue_with_wrong_version_is_not_repaired(tmp_path):
    store, original, development = case(tmp_path)
    result = moderator(development.proposed_revision, [issue('new', version=9)])
    derived, _, references = derive_claim_versions(original, result, new_issue_contract=True)
    assert derived.updated_issues[0].claim_version == 9 and not references
    card = store.save_card(derived.proposed_card_revision, card_id=original.card_id, parent_version=1)
    run = store.create_run('run', card_id=card.card_id, card_version=card.version)
    with pytest.raises(StateError, match='issue_refers_to_unknown_claim_version'):
        store.apply_issues(run.run_id, derived.updated_issues, derived.issue_transitions)


class ConditionsRuntime(ScriptedRuntime):
    def __init__(self, store, *, mode='developer', keep_evidence=False):
        super().__init__(store)
        self.mode, self.keep_evidence = mode, keep_evidence

    def reply(self, role, task, payload, task_id):
        result = super().reply(role, task, payload, task_id)
        if role == self.mode == 'developer':
            proposed = result['proposed_revision']
        elif role == self.mode == 'moderator':
            proposed = deepcopy(payload['card']['draft'])
            result['proposed_card_revision'] = proposed
        else:
            return result
        revised = proposed['claims'][0]
        revised['conditions'].append('Only cases with a validated positive control.')
        if not self.keep_evidence:
            revised['evidence_ids'] = []
        if role == 'developer':
            result['affected_claims'] = [revised['claim_id']]
            result['evidence_review'] = [{'claim_id': revised['claim_id'], 'claim_version': revised['version'],
                'evidence_ids': list(revised['evidence_ids']), 'still_applicable': True,
                'explanation': 'The proposed narrower condition still requires its own evidence.'}]
        return result


def workflow_case(tmp_path, *, mode='develop', keep_evidence=False):
    store, _, evidence = research_store(tmp_path)
    draft = research_draft()
    draft.claims = [Claim(claim_id='claim_observation', version=1,
        text='Distance and distractor count covary.', conditions=['synthetic controlled recall task'],
        kind='empirical', evidence_ids=[evidence.evidence_id] if keep_evidence else [])]
    card = store.save_card(draft)
    run = store.create_run(mode, card_id=card.card_id, card_version=card.version)
    runtime = ConditionsRuntime(store, mode='developer' if mode == 'develop' else 'moderator',
                                keep_evidence=keep_evidence)
    return store, card, run, runtime, evidence


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['develop', 'run'])
async def test_workflow_persists_derivation_and_resumes_after_saved_card_without_replay(tmp_path, monkeypatch, mode):
    store, original, run, runtime, evidence = workflow_case(tmp_path, mode=mode)
    engine = WorkflowEngine(store, runtime, Settings())
    actual_save = store.save_card

    def crash_after_save(*args, **kwargs):
        result = actual_save(*args, **kwargs)
        raise SystemExit('Synthetic crash after the new card became durable.')

    monkeypatch.setattr(store, 'save_card', crash_after_save)
    with pytest.raises(SystemExit):
        await engine.execute(run.run_id)
    key = 'development' if mode == 'develop' else 'round1.moderator'
    state = store.get_run(run.run_id).state
    audit_path = state['claim_version_derivations'][key]
    audit_text = store.read_artifact(audit_path)
    audit = json.loads(audit_text)
    assert len(audit['version_changes']) == 1 and audit['verification_transferred'] is False
    assert audit['version_changes'][0]['changed_fields'] == ['conditions']
    task = store.get_task(f'{run.run_id}.{key}')
    raw_artifact = store.read_artifact(task.response_artifact_path)
    assert audit['source_tasks'][0]['response_artifact_path'] == task.response_artifact_path
    raw_field = 'proposed_revision' if mode == 'develop' else 'proposed_card_revision'
    assert state[key][raw_field]['claims'][0]['version'] == 1
    assert task.accepted_result['result'][raw_field]['claims'][0]['version'] == 1
    assert store.get_card(original.card_id).draft.claims[0].version == 2
    calls = Counter(c['role'] for c in runtime.calls)
    monkeypatch.setattr(store, 'save_card', actual_save)
    resumed = await WorkflowEngine(Store(store.db_path), runtime, Settings()).execute(run.run_id)
    assert resumed.status == 'COMPLETED' and resumed.card_version == 2
    assert Counter(c['role'] for c in runtime.calls)['investigator'] == calls['investigator']
    assert Counter(c['role'] for c in runtime.calls)[runtime.mode] == calls[runtime.mode]
    assert store.read_artifact(audit_path) == audit_text
    assert store.read_artifact(task.response_artifact_path) == raw_artifact
    assert store.get_card(original.card_id, 1).draft == original.draft
    assert store.list_evidence(ids=[evidence.evidence_id])[0] == evidence
    assert store.get_card(original.card_id).version == 2


@pytest.mark.asyncio
async def test_increment_removes_old_target_without_upgrading_evidence(tmp_path):
    store, original, run, runtime, evidence = workflow_case(tmp_path, keep_evidence=True)
    result = await WorkflowEngine(store, runtime, Settings()).execute(run.run_id)
    assert result.status == 'COMPLETED'
    path = result.state['claim_version_derivations']['development']
    derived = json.loads(store.read_artifact(path))['derived_result']
    assert derived['proposed_revision']['claims'][0]['version'] == 2
    assert derived['proposed_revision']['claims'][0]['evidence_ids'] == []
    assert derived['evidence_review'][0]['claim_version'] == 2
    assert derived['evidence_review'][0]['still_applicable'] is True
    assert store.list_evidence(ids=[evidence.evidence_id])[0] == evidence
    assert store.get_card(original.card_id).version == 2
    assert store.get_card(original.card_id, 1).draft.claims[0].evidence_ids == [evidence.evidence_id]
    recheck = next(c for c in runtime.calls if c['task_id'].endswith('development.evidence_recheck'))
    assert recheck['payload']['card']['draft']['claims'][0]['version'] == 2
    assert recheck['payload']['fresh_verification_required'] is False
    proposer = next(c for c in runtime.calls if c['role'] == 'proposer')
    removal = proposer['payload']['claim_evidence_reselection']['development']
    assert removal['removed_references'][0]['evidence_id'] == evidence.evidence_id
    assert removal['evidence_review_status'] == 'original_proposal_not_current_evidence_applicability'


@pytest.mark.asyncio
async def test_new_moderator_issue_cannot_be_resolved_by_previous_version_evidence(tmp_path):
    store, original, run, _, evidence = workflow_case(tmp_path, mode='run')

    class InvalidResolution(ConditionsRuntime):
        def reply(self, role, task, payload, task_id):
            result = super().reply(role, task, payload, task_id)
            if role == 'moderator':
                problem = issue('new_condition_issue')
                problem.update(claim_id='claim_observation', claim_kind='empirical', status='resolved',
                               evidence_ids=[evidence.evidence_id])
                result['updated_issues'] = [problem]
                result['issue_transitions'] = [{'issue_id': problem['issue_id'], 'from_status': None,
                    'to_status': 'resolved', 'change_this_round': 'Claimed resolution from an earlier passage.',
                    'basis_evidence_ids': [evidence.evidence_id], 'basis_argument': None,
                    'resolution_reason': 'The model incorrectly treats the old target as verified here.'}]
            return result

    runtime = InvalidResolution(store, mode='moderator')
    result = await WorkflowEngine(store, runtime, Settings()).execute(run.run_id)
    assert result.status == 'PAUSED_PROTOCOL'
    assert result.stop_reason == 'empirical_resolution_requires_verified_claim_evidence'
    audit = json.loads(store.read_artifact(result.state['claim_version_derivations']['round1.moderator']))
    assert audit['reference_updates'][0]['path'] == 'updated_issues.0.claim_version'
    assert audit['derived_result']['updated_issues'][0]['claim_version'] == 2
    assert audit['derived_result']['updated_issues'][0]['status'] == 'resolved'  # Not silently rewritten.
    assert store.get_issues(run.run_id) == []  # The invalid resolution was never accepted.
    assert store.list_evidence(ids=[evidence.evidence_id])[0] == evidence
