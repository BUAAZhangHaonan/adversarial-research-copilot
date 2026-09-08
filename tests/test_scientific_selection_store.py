"""New scientific judgments remain their own immutable records."""
import json

import pytest

from arc.schemas import ScientificReview
from arc.store import StateError
from tests.test_semantic_claim_edits import setup_claim


def scientific_review(action='retain'):
    return ScientificReview(original_question='Which controlled variable explains the observation?',
        scope_faithful=True, core_insight='One missing contrast separates two plausible explanations.',
        value_judgment='substantial', value_reason='The answer changes the choice of intervention.',
        verification_work=[{'question': 'Does each contrast have an experimental cell?',
            'method': 'derivation', 'answer': 'Every term maps to a declared condition.',
            'evidence_ids': [], 'source_ids': []}], decisive_findings=[], prior_findings=[],
        edit_assessments=[], remaining_uncertainty=['The empirical result remains unmeasured.'], action=action)


@pytest.mark.parametrize('action,selection,assessment', [('retain', 'MAIN_REPORT', 'PROMISING'),
    ('needs_evidence', 'LEAD_ONLY', 'NEEDS_EVIDENCE'), ('reject', 'NOT_RETAINED', 'REJECTED')])
def test_scientific_selection_roundtrips_without_old_supported_labels(tmp_path, action, selection, assessment):
    store, _, _, card = setup_claim(tmp_path)
    run = store.create_run('discover')
    review = scientific_review(action)
    with store._connect() as db:
        card_before = db.execute('SELECT data FROM cards WHERE card_id=?', (card.card_id,)).fetchone()[0]
    accepted = store.record_selection(run.run_id, card.card_id, card.version, review)
    assert accepted.selection == selection and accepted.assessment == assessment
    assert isinstance(accepted.selection_result, ScientificReview)
    assert accepted.selection_result == review
    assert store.get_card(card.card_id).selection_result == review
    assert store.list_cards(run_id=run.run_id)[0].selection_result == review
    with store._connect() as db:
        stored = json.loads(db.execute('SELECT data FROM selections WHERE card_id=?', (card.card_id,)).fetchone()[0])
        assert db.execute('SELECT data FROM cards WHERE card_id=?', (card.card_id,)).fetchone()[0] == card_before
    assert stored == review.model_dump(mode='json')
    assert 'selection_checks' not in stored and 'supported' not in json.dumps(stored)
    assert store.record_selection(run.run_id, card.card_id, card.version, review) == accepted
    changed = review.model_copy(update={'value_reason': 'A different later judgment.'})
    with pytest.raises(StateError, match='selection_already_accepted'):
        store.record_selection(run.run_id, card.card_id, card.version, changed)
