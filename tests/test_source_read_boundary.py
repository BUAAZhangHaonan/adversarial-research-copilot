"""An unavailable page is an actionable read failure, not successful empty evidence."""
import pytest
from arc.runtime import build_tools
from arc.schemas import SourceRecord
from arc.store import Store


@pytest.mark.asyncio
@pytest.mark.parametrize('complete,offset,error', [
    (False, 8, 'SOURCE_CACHE_EXHAUSTED'),
    (False, 10000, 'SOURCE_CACHE_EXHAUSTED'),
    (True, 8, 'SOURCE_END_REACHED'),
    (True, 10000, 'SOURCE_END_REACHED'),
])
async def test_empty_page_distinguishes_missing_cache_from_original_end(tmp_path, complete, offset, error):
    store = Store(tmp_path / 'arc.sqlite')
    source = store.register_source(SourceRecord(title='Original', url='https://example.org/paper',
        source_type='paper', access_status='retrieved', content_origin='original',
        content_complete=complete, content_total_chars=8 if complete else 20), content='abcdefgh')
    before = source.model_dump(mode='json')
    tools = build_tools(store)
    result = await tools['read_record'].handler({'record_id':source.source_id, 'offset':offset, 'limit':300}, {})
    assert result['is_error'] is True and result['error'] == error
    assert result['content'] == '' and result['next_cached_offset'] is None
    assert (result['cached_range_start'], result['cached_range_end']) == (0, 8)
    assert result['requires_source_fetch'] is (not complete)
    assert result['url'] == source.url and result['source_id'] == source.source_id
    assert store.get_source(source.source_id).model_dump(mode='json') == before
    # Re-reading an actually cached page still succeeds; no permanent task lock.
    actual = await tools['read_record'].handler({'record_id':source.source_id, 'offset':6, 'limit':64000}, {})
    assert actual['content'] == 'gh' and not actual.get('is_error')
    assert actual['requires_source_fetch'] is (not complete)
