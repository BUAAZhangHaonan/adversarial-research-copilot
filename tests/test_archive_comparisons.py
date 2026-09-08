"""Required archive coverage coexists with real additional paginated records."""

import pytest

from arc.schemas import EvidenceRecord, LibrarianResult, SourceRecord
from arc.validation import ProtocolViolation, validate_archive_comparisons
from tests.test_selection import research_draft, research_store


def cards(store):
    draft = research_draft()
    draft.motivation.evidence_ids = []
    draft.closest_work_delta.source_ids = []
    return [store.save_card(draft) for _ in range(2)]


def records(card):
    return [{'card_id': card.card_id, 'version': card.version,
             'reopen_conditions': card.draft.risks.reopen_conditions}]


def result_for(*items):
    return LibrarianResult(comparisons=[{'archive_card_id': card.card_id,
        'archive_card_version': card.version, 'relation': 'related_but_distinct',
        'rationale': 'The intervention differs.', 'reopening_condition_met': False}
        for card in items], records_opened=[], retrieval_scope='Initial recall and an additional page.',
        unsearched_limits=[], needs_additional_lookup=False)


def invalid_result(valid, kind):
    result = valid.model_copy(deep=True)
    if kind == 'missing':
        result.comparisons = result.comparisons[1:]
    elif kind == 'duplicate':
        result.comparisons.append(result.comparisons[0].model_copy())
    elif kind == 'unknown':
        result.comparisons[1].archive_card_id = 'card_nonexistent'
    else:
        result.comparisons[1].archive_card_version = 999
    return result


def test_real_extra_card_version_is_accepted_without_changing_output(tmp_path):
    store, _, _ = research_store(tmp_path)
    first, extra = cards(store)
    result = result_for(first, extra)
    before = result.model_dump(mode='json')
    validate_archive_comparisons(result, records(first), store)
    assert result.model_dump(mode='json') == before


@pytest.mark.parametrize('kind,diagnostic', [('missing', 'missing'), ('duplicate', 'duplicates'),
    ('unknown', 'ARCHIVE_COMPARISON_UNKNOWN_CARD'), ('wrong_version', 'ARCHIVE_COMPARISON_UNKNOWN_CARD')])
def test_missing_duplicate_unknown_or_wrong_version_gives_addressed_diagnostic(tmp_path, kind, diagnostic):
    store, _, _ = research_store(tmp_path)
    first, extra = cards(store)
    with pytest.raises(ProtocolViolation, match=diagnostic) as caught:
        validate_archive_comparisons(invalid_result(result_for(first, extra), kind), records(first), store)
    assert 'comparisons' in str(caught.value)
    assert first.card_id in str(caught.value) if kind in {'missing', 'duplicate'} else ('card_nonexistent' in str(caught.value) if kind == 'unknown' else '999' in str(caught.value))


def test_extra_reopening_uses_actual_recorded_condition_and_requires_new_registered_evidence(tmp_path):
    store, source, evidence = research_store(tmp_path)
    first, extra = cards(store)
    # The extra card previously used this evidence.
    draft = extra.draft.model_copy(deep=True)
    draft.motivation.evidence_ids = [evidence.evidence_id]
    extra = store.save_card(draft, card_id=extra.card_id, parent_version=extra.version)
    result = result_for(first, extra)
    relation = result.comparisons[1]
    relation.relation = 'reopening_candidate'
    relation.reopening_condition = extra.draft.risks.reopen_conditions[0]
    relation.new_evidence_ids = [evidence.evidence_id]
    relation.reopening_condition_met = True
    with pytest.raises(ProtocolViolation, match='REOPENING_REQUIRES_NEW_EVIDENCE'):
        validate_archive_comparisons(result, records(first), store)
    text = 'New evidence separates the two factors.'
    new_source = store.register_source(SourceRecord(title='New controlled result', url=None, source_type='user_material',
        access_status='retrieved', content_origin='original'), content=text)
    new_evidence = store.register_evidence(EvidenceRecord(source_id=new_source.source_id, claim_id='new_control', claim_version=1,
        claim='The two factors can be independently manipulated.', conditions=['synthetic task'],
        locator=f'chars:0:{len(text)}', excerpt=text, relation='supports', origin='original',
        locator_status='verified', verification_status='verified', support_explanation='The new passage reports separation.'))
    relation.new_evidence_ids = [new_evidence.evidence_id]
    validate_archive_comparisons(result, records(first), store)
    relation.reopening_condition = 'An invented condition'
    with pytest.raises(ProtocolViolation, match='REOPENING_CONDITION_NOT_RECORDED'):
        validate_archive_comparisons(result, records(first), store)
