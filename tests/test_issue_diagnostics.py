import pytest
from arc.schemas import Issue, IssueTransition
from arc.store import StateError, claim_fingerprint
from tests.test_store import store, source, evidence
from tests.test_contracts import card_payload


def setup_resolution(store, version):
    payload = card_payload()
    payload['claims'] = [{'claim_id': 'C1', 'version': 2, 'text': 'A controlled observation.',
                          'conditions': ['synthetic'], 'kind': 'empirical', 'evidence_ids': []}]
    card = store.save_card(payload)
    run = store.create_run('run', card_id=card.card_id, card_version=card.version)
    ev = evidence(store, source(store), claim_id='C1', claim_version=version, relation='supports',
                  target_claim_fingerprint=claim_fingerprint(card.draft.claims[0]))
    issue = Issue(issue_id='I1', claim_id='C1', claim_version=2, content='Empirical concern',
                  status='resolved', evidence_ids=[ev.evidence_id], resolution_criterion='Targeted evidence',
                  change_this_round='Source checked', next_action='STOP')
    transition = IssueTransition(issue_id='I1', from_status=None, to_status='resolved',
                                change_this_round='Source checked', basis_evidence_ids=[ev.evidence_id],
                                basis_argument=None, resolution_reason='Observed target evidence')
    return run, issue, transition


def test_issue_dry_run_checks_success_without_persisting_state_or_events(store):
    run, issue, transition = setup_resolution(store, 2)
    result = store.apply_issues(run.run_id, [issue], [transition], event_key='round1',
                               state_patch={'rounds_completed': 1}, dry_run=True)
    assert result == [issue]
    assert store.get_run(run.run_id) == run
    assert store.get_issues(run.run_id) == []
    with store._connect() as db:
        assert db.execute('SELECT count(*) FROM issue_events').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM issue_applied').fetchone()[0] == 0
    store.apply_issues(run.run_id, [issue], [transition], event_key='round1', state_patch={'rounds_completed': 1})
    assert store.get_run(run.run_id).state['rounds_completed'] == 1
    assert store.get_issues(run.run_id) == [issue]


@pytest.mark.parametrize('dry_run', [False, True])
def test_old_version_resolution_reports_exact_issue_and_evidence_without_changing_gate(store, dry_run):
    run, issue, transition = setup_resolution(store, 1)
    with pytest.raises(StateError, match='empirical_resolution_requires_verified_claim_evidence') as caught:
        store.apply_issues(run.run_id, [issue], [transition], dry_run=dry_run)
    diagnostic = caught.value.diagnostics[0]
    assert diagnostic['issue_id'] == 'I1'
    assert diagnostic['loc'] == ['result', 'issue_transitions', 0, 'basis_evidence_ids']
    assert diagnostic['expected_claim'] == {'claim_id': 'C1', 'claim_version': 2}
    assert diagnostic['provided_evidence'][0]['claim_version'] == 1
    assert diagnostic['provided_evidence'][0]['verification_status'] == 'verified'
    assert store.get_issues(run.run_id) == []
    assert store.get_run(run.run_id) == run
