"""Explicit independent meaning reviews preserve evidence originals across edits."""
import copy
import json

import pytest

from arc.schemas import Claim, Issue, IssueTransition, TaskRecord
from arc.store import StateError, claim_fingerprint
from arc.validation import ProtocolViolation, derive_claim_versions, remove_superseded_claim_evidence
from tests.test_selection import research_draft, research_store


def setup_claim(tmp_path):
    store, source, evidence = research_store(tmp_path)
    draft = research_draft()
    claim = Claim(claim_id=evidence.claim_id, version=1, text=evidence.claim,
        conditions=evidence.conditions, kind='empirical', evidence_ids=['ev_target'])
    target = store.register_evidence(evidence.model_copy(update={'evidence_id': 'ev_target',
        'relation': 'supports', 'target_claim_fingerprint': claim_fingerprint(claim)}))
    draft.claims = [claim]
    card = store.save_card(draft)
    return store, source, target, card


def reviewed_task(store, original, proposed, assessments, *, role='scientific_reviewer.INVOKE', scope_faithful=True):
    run = store.create_run('develop', card_id=original.card_id, card_version=original.version)
    subject = {'campaign_id': None, 'run_id': run.run_id,
        'card_id': original.card_id, 'card_version': original.version}
    key = 'independent_review'
    task_id = run.run_id + '.' + key
    payload = {'original_card': original.model_dump(mode='json'), 'proposed_revision': proposed.model_dump(mode='json')}
    store.update_run(run.run_id, state={'task_inputs': {key: {'subject': subject, 'payload': payload}}})
    accepted = {'schema_version': 'arc.v1', 'task_id': task_id, 'subject': subject,
        'result_status': 'complete', 'result': {'edit_assessments': assessments, 'scope_faithful': scope_faithful},
        'evidence_requests': [], 'capability_requests': [], 'note': None}
    prompt = store.save_artifact(f'tests/{task_id}.prompt.json', json.dumps({'prompt_id': role}))
    raw = store.save_artifact(f'tests/{task_id}.response.json', json.dumps({'response': {'message': {'content': json.dumps(accepted)}}}))
    record = TaskRecord(task_id=task_id, run_id=run.run_id, status='ACCEPTED',
        input_hash='fixture', prompt_hash='fixture', model_config_hash='fixture',
        rendered_prompt_path=prompt, response_artifact_path=raw, accepted_result=accepted)
    store.put_task(record)
    return store.get_task(task_id)


def assessment(card, kind='unchanged_meaning'):
    return [{'claim_id': card.draft.claims[0].claim_id, 'change_kind': kind,
        'reason': 'The same quoted observation and population are retained; the edit only clarifies the non-exhaustive example wording.'}]


def edited_card(card):
    proposed = card.draft.model_copy(deep=True)
    proposed.claims[0].text += ' This describes the observed covariation, without adding a causal assertion.'
    return proposed


def save_reviewed(store, original, proposed, reviews):
    task = reviewed_task(store, original, proposed, reviews)
    derived, changes, _ = derive_claim_versions(original, proposed, edit_assessments=reviews)
    derived, removed = remove_superseded_claim_evidence(store, derived)
    saved = store.save_card(derived, card_id=original.card_id, parent_version=original.version,
        edit_assessments=reviews, review_task_id=task.task_id)
    return saved, task, changes, removed


@pytest.mark.parametrize('submitted_version', [1, 2])
def test_reviewed_expression_edit_preserves_semantic_version_and_immutable_evidence(tmp_path, submitted_version):
    store, source, evidence, original = setup_claim(tmp_path)
    proposed = edited_card(original)
    proposed.claims[0].version = submitted_version
    original_bytes = store.read_artifact(source.content_path)
    with pytest.raises(StateError, match='changed_claim_requires_new_version|claim_evidence_version_mismatch'):
        store.save_card(proposed, card_id=original.card_id, parent_version=1)
    saved, task, changes, removed = save_reviewed(store, original, proposed, assessment(original))
    assert saved.version == 2 and saved.draft.claims[0].version == 1
    assert saved.draft.claims[0].evidence_ids == [evidence.evidence_id]
    assert changes[0]['change_kind'] == 'unchanged_meaning' and removed == []
    assert store.get_card(original.card_id, 1) == original
    assert store.list_evidence(ids=[evidence.evidence_id]) == [evidence]
    assert store.read_artifact(source.content_path) == original_bytes
    review = store.list_claim_edit_reviews(saved.card_id, saved.version)[0]
    assert review['review_task_id'] == task.task_id
    assert review['original_claim']['text'] == original.draft.claims[0].text
    assert review['revised_claim']['text'] == proposed.claims[0].text
    assert review['evidence_originals_modified'] is False
    binding = store.claim_evidence_bindings(saved.draft)[0]
    assert binding['binding'] == 'reviewed_equivalent_claim_target'
    assert binding['equivalence_reviews'][0]['review_task_id'] == task.task_id
    assert binding['verification_transferred'] is False
    assert binding['support_semantics'] == 'requires_scientific_review_not_proven_by_source_verification'


@pytest.mark.parametrize('scope_faithful', [True, False])
def test_independent_review_can_allow_method_condition_edit_without_changing_original_scope(tmp_path, scope_faithful):
    store, _, _, original = setup_claim(tmp_path)
    proposed = original.draft.model_copy(deep=True)
    proposed.problem_anchor.conditions.append('The implementation budget is a proposal detail, not a user constraint.')
    with pytest.raises(StateError, match='problem_anchor_changed'):
        store.save_card(proposed, card_id=original.card_id, parent_version=1)
    task = reviewed_task(store, original, proposed, [], scope_faithful=scope_faithful)
    if scope_faithful:
        updated = store.save_card(proposed, card_id=original.card_id, parent_version=1,
            review_task_id=task.task_id)
        assert updated.version == 2 and updated.draft.problem_anchor == proposed.problem_anchor
    else:
        with pytest.raises(StateError, match='problem_anchor_changed'):
            store.save_card(proposed, card_id=original.card_id, parent_version=1, review_task_id=task.task_id)
        assert store.get_card(original.card_id).version == 1
    assert store.get_card(original.card_id, 1) == original


def test_multiple_equivalent_edits_form_review_chain_without_rebinding_original(tmp_path):
    store, _, evidence, original = setup_claim(tmp_path)
    current, first, _, _ = save_reviewed(store, original, edited_card(original), assessment(original))
    latest, second, _, _ = save_reviewed(store, current, edited_card(current), assessment(current))
    assert latest.version == 3 and latest.draft.claims[0].version == 1
    assert store.evidence_targets_claim(evidence, latest.draft.claims[0])
    path = store.claim_equivalence_reviews(evidence, latest.draft.claims[0])
    assert [item['review_task_id'] for item in path] == [first.task_id, second.task_id]
    assert store.list_evidence(ids=[evidence.evidence_id]) == [evidence]


def test_substantive_change_increments_only_affected_claim_and_removes_its_old_support(tmp_path):
    store, _, evidence, original = setup_claim(tmp_path)
    untouched = Claim(claim_id='other_hypothesis', version=1, text='A separate untested prediction.',
        conditions=[], kind='hypothesis', evidence_ids=[evidence.evidence_id])
    parent_draft = original.draft.model_copy(deep=True)
    parent_draft.claims.append(untouched)
    parent = store.save_card(parent_draft, card_id=original.card_id, parent_version=1)
    proposed = parent.draft.model_copy(deep=True)
    proposed.claims[0].conditions = ['All tasks, including populations absent from the original source.']
    saved, _, changes, removed = save_reviewed(store, parent, proposed, assessment(parent, 'substantive'))
    assert saved.draft.claims[0].version == 2 and saved.draft.claims[0].evidence_ids == []
    assert saved.draft.claims[1] == untouched
    assert len(changes) == len(removed) == 1 and removed[0]['evidence_id'] == evidence.evidence_id
    assert not store.evidence_targets_claim(evidence, saved.draft.claims[0])
    assert store.list_evidence(ids=[evidence.evidence_id]) == [evidence]


@pytest.mark.parametrize('invalid', ['no_review_task', 'wrong_role', 'changed_reason', 'changed_draft', 'missing_assessment'])
def test_equivalence_requires_exact_independent_review_and_frozen_inputs(tmp_path, invalid):
    store, _, evidence, original = setup_claim(tmp_path)
    proposed = edited_card(original)
    reviews = assessment(original)
    task = reviewed_task(store, original, proposed, reviews,
        role='developer.INVOKE' if invalid == 'wrong_role' else 'scientific_reviewer.INVOKE')
    if invalid == 'changed_reason': reviews[0]['reason'] = 'A reason not provided by the reviewer.'
    if invalid == 'changed_draft': proposed.method.simplest_path = 'A method the reviewer never saw.'
    if invalid == 'missing_assessment': reviews = []
    with pytest.raises((StateError, ProtocolViolation)):
        store.save_card(proposed, card_id=original.card_id, parent_version=1,
            edit_assessments=reviews, review_task_id=None if invalid == 'no_review_task' else task.task_id)
    assert store.get_card(original.card_id).version == 1
    assert store.list_claim_edit_reviews() == []
    assert store.list_evidence(ids=[evidence.evidence_id]) == [evidence]


@pytest.mark.parametrize('change', ['kind', 'addition', 'deletion'])
def test_equivalence_cannot_hide_identity_or_kind_change(tmp_path, change):
    store, _, _, original = setup_claim(tmp_path)
    proposed = original.draft.model_copy(deep=True)
    reviews = assessment(original)
    if change == 'kind': proposed.claims[0].kind = 'hypothesis'
    elif change == 'deletion': proposed.claims = []
    else:
        new = proposed.claims[0].model_copy(update={'claim_id': 'new_claim'})
        proposed.claims.append(new)
        reviews = [{**reviews[0], 'claim_id': 'new_claim'}]
    with pytest.raises(ProtocolViolation, match='EQUIVALENCE_CANNOT_CHANGE_IDENTITY_OR_KIND'):
        derive_claim_versions(original, proposed, edit_assessments=reviews)


def test_equivalent_target_can_close_empirical_issue_without_changing_verified_original(tmp_path):
    store, _, evidence, original = setup_claim(tmp_path)
    saved, _, _, _ = save_reviewed(store, original, edited_card(original), assessment(original))
    run = store.create_run('run', card_id=saved.card_id, card_version=saved.version)
    issue = Issue(issue_id='observation', claim_id=evidence.claim_id, claim_version=1,
        content='Does this observation occur?', status='resolved', evidence_ids=[evidence.evidence_id],
        resolution_criterion='Current equivalent observation supported by the original passage.',
        change_this_round='Independent meaning review retained the same assertion.', next_action='STOP')
    transition = IssueTransition(issue_id=issue.issue_id, from_status=None, to_status='resolved',
        change_this_round=issue.change_this_round, basis_evidence_ids=[evidence.evidence_id],
        basis_argument=None, resolution_reason='The preserved original supports the same observation.')
    store.apply_issues(run.run_id, [issue], [transition])
    assert store.get_issues(run.run_id)[0].status == 'resolved'
    assert store.list_evidence(ids=[evidence.evidence_id]) == [evidence]
