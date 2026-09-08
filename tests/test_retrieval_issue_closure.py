"""Retrieval exhaustion does not settle an unresolved scientific question."""
import pytest
from arc.schemas import Issue, IssueTransition
from arc.store import StateError
from tests.test_semantic_claim_edits import setup_claim


@pytest.mark.parametrize('final_status', ['resolved', 'withdrawn'])
def test_ending_retrieval_does_not_resolve_missing_scientific_support_but_allows_withdrawal(tmp_path, final_status):
    store, _, evidence, original = setup_claim(tmp_path)
    draft = original.draft.model_copy(deep=True)
    draft.claims[0].kind = 'logical'
    draft.claims[0].version = 2
    draft.claims[0].evidence_ids = []
    saved = store.save_card(draft, card_id=original.card_id, parent_version=1)
    run = store.create_run('run', card_id=saved.card_id, card_version=saved.version)
    issue = Issue(issue_id='nearest_work', claim_id=evidence.claim_id, claim_version=2, claim_kind='logical',
        content='A potentially decisive nearest work has not been read.', status='needs_retrieval', evidence_ids=[],
        resolution_criterion='Read the methods before assessing coverage.', change_this_round='Methods remain inaccessible.', next_action='RETRIEVE')
    opened = IssueTransition(issue_id=issue.issue_id, from_status=None, to_status=issue.status,
        change_this_round=issue.change_this_round, basis_evidence_ids=[], basis_argument=None, resolution_reason=None)
    store.apply_issues(run.run_id, [issue], [opened])
    changed = issue.model_copy(update={'status': final_status, 'next_action': 'STOP'})
    ended = opened.model_copy(update={'from_status': 'needs_retrieval', 'to_status': final_status,
        'basis_argument': 'The retrieval attempt has ended; we can instead withdraw this unsupported assertion.',
        'resolution_reason': 'No further request is planned.'})
    if final_status == 'resolved':
        with pytest.raises(StateError, match='retrieval_resolution_requires_verified_claim_evidence'):
            store.apply_issues(run.run_id, [changed], [ended])
        assert store.get_issues(run.run_id)[0].status == 'needs_retrieval'
    else:
        store.apply_issues(run.run_id, [changed], [ended])
        assert store.get_issues(run.run_id)[0].status == 'withdrawn'
