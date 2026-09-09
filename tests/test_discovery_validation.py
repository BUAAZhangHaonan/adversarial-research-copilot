"""Actual source availability and material-progress checks, with no model calls."""
from copy import deepcopy

import pytest

from arc.discovery_models import FieldBrief, SourceNote, CandidateCheck, IdeaNote, IdeaSeed, ResourceHint
from arc.discovery_validation import repeated_exhausted_read, validate_source_access
from arc.schemas import SourceRecord
from arc.store import Store


def brief(source, access):
    return FieldBrief(overview='Literature overview', research_lines=[], openings=[],
        source_notes=[SourceNote(source_id=source.source_id, finding='A scoped observation',
            relevance='Relevant to this question', access=access)], search_limits=[])


def source_store(tmp_path, *, content='Original text.', **changes):
    store = Store(tmp_path / 'state.sqlite')
    values = dict(title='Fixture', url='https://example.test/fixture', source_type='user_material',
        access_status='retrieved', content_origin='original', content_complete=True)
    values.update(changes)
    source = store.register_source(SourceRecord(**values), content=content)
    return store, source


@pytest.mark.parametrize('access', ['passage', 'full_text', 'code'])
def test_metadata_does_not_become_primary_material(tmp_path, access):
    store, source = source_store(tmp_path, content=None, content_origin='metadata',
                                 access_status='metadata_only')
    with pytest.raises(ValueError, match='source_access_exceeds'):
        validate_source_access(store, brief(source, access))
    validate_source_access(store, brief(source, 'metadata'))


def test_truncated_text_is_a_passage_not_full_text(tmp_path):
    store, source = source_store(tmp_path, content_complete=False, content_total_chars=1000)
    validate_source_access(store, brief(source, 'passage'))
    with pytest.raises(ValueError, match='source_full_text_not_available'):
        validate_source_access(store, brief(source, 'full_text'))


def test_empty_original_file_is_not_a_read_passage(tmp_path):
    store, source = source_store(tmp_path, content='   ')
    with pytest.raises(ValueError, match='source_retrieved_content_empty'):
        validate_source_access(store, brief(source, 'passage'))


def test_original_body_and_code_are_available_without_claiming_semantic_proof(tmp_path):
    store, source = source_store(tmp_path)
    validate_source_access(store, brief(source, 'full_text'))
    with pytest.raises(ValueError, match='source_is_not_original_code'):
        validate_source_access(store, brief(source, 'code'))


def test_secondary_text_is_not_original_abstract(tmp_path):
    store, source = source_store(tmp_path, content_origin='secondary_analysis',
                                 source_type='secondary_analysis')
    validate_source_access(store, brief(source, 'secondary'))
    with pytest.raises(ValueError, match='secondary_analysis_is_not_original_abstract'):
        validate_source_access(store, brief(source, 'abstract'))


def test_check_field_updates_receive_same_source_validation(tmp_path):
    store, source = source_store(tmp_path, content=None, content_origin='metadata',
                                 access_status='metadata_only')
    note = IdeaNote(seed=IdeaSeed(title='Idea', question='Question?', insight='Insight',
        why_it_matters='Value', difference_from_known='Difference', source_ids=[], key_unknown='Unknown'),
        decision='lead', reason='Preliminary', nearest_work=[], feasibility='Unknown',
        resources=ResourceHint(basis='No estimate'), main_risk='Risk', next_question='Next?',
        source_notes=[], limits=[], changes_from_seed=[])
    result = CandidateCheck(note=note, field_updates=brief(source, 'full_text').source_notes)
    with pytest.raises(ValueError, match='source_access_exceeds'):
        validate_source_access(store, result)


def eof(**changes):
    result = dict(source_id='source', version='1', representation_id='markdown',
        cached_content_chars=100, content_total_chars=200, content='',
        error='SOURCE_CACHE_EXHAUSTED', is_error=True)
    result.update(changes)
    return {'name': 'read_record', 'arguments': {'record_id': result['source_id'], 'offset': 100},
            'result': result}


def page(start=0, length=50, **changes):
    result = dict(source_id='source', version='1', representation_id='markdown',
        cached_content_chars=100, content_total_chars=200, content='x' * length,
        content_offset=start, is_error=False)
    result.update(changes)
    return {'name': 'read_record', 'arguments': {'record_id': result['source_id'], 'offset': start},
            'result': result}


def fetch(**changes):
    source = dict(source_id='source', version='1', representation_id='markdown',
                  content_origin='original', content_chars=200)
    source.update(changes)
    return {'name': 'read_paper', 'result': {'is_error': False, 'sources': [source]}}


@pytest.mark.parametrize('error', ['SOURCE_CACHE_EXHAUSTED', 'SOURCE_END_REACHED'])
def test_first_eof_is_feedback_repeated_same_boundary_stops(error):
    assert not repeated_exhausted_read([eof(error=error)])
    assert repeated_exhausted_read([eof(error=error), eof(error=error)])


@pytest.mark.parametrize('progress', [page(), page(start=50),
    fetch(), fetch(representation_id='pdf'),
    eof(cached_content_chars=200), eof(representation_id='pdf')])
def test_later_progress_supersedes_old_repeated_eof(progress):
    assert not repeated_exhausted_read([eof(), eof(), progress])


def test_repeated_old_page_is_not_new_progress_but_new_range_is():
    old = page()
    assert repeated_exhausted_read([old, eof(), eof(), old])
    assert not repeated_exhausted_read([old, eof(), eof(), page(start=50)])
    # Two already read adjacent ranges also cover a later combined read.
    assert repeated_exhausted_read([page(), page(start=50), eof(), eof(), page(length=100)])


def test_repeating_identical_fetch_or_search_metadata_cannot_reset_guard():
    prior = fetch(content_chars=100)
    assert repeated_exhausted_read([prior, eof(), eof(), prior])
    assert repeated_exhausted_read([eof(), eof(), fetch(content_origin='metadata', content_chars=0)])
    assert repeated_exhausted_read([eof(), eof(), {'name':'read_paper',
        'result': {'is_error':True, 'sources': [fetch()['result']['sources'][0]]}}])


def test_after_genuine_progress_a_new_repeated_boundary_still_stops():
    grown = eof(cached_content_chars=200)
    assert repeated_exhausted_read([eof(), eof(), fetch(), grown, grown])


def test_different_sources_do_not_share_eof_count_and_arguments_supply_identity():
    assert not repeated_exhausted_read([eof(), eof(source_id='other')])
    first = eof()
    first['result'].pop('source_id')
    assert repeated_exhausted_read([first, deepcopy(first)])
    missing = {'name': 'read_record', 'result': {'error':'SOURCE_END_REACHED'}}
    assert not repeated_exhausted_read([missing, missing])


def test_retrieved_repository_page_is_not_rejected_by_transport_classification(tmp_path):
    store, source = source_store(tmp_path, content='def policy(observation): return observation',
                                  source_type='web_unclassified')
    validate_source_access(store, brief(source, 'code'))
    assert store.get_source(source.source_id).source_type == 'web_unclassified'
