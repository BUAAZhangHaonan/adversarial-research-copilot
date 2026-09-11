from tests.test_mcp_content import page, replay
from arc.store import Store
import pytest


@pytest.mark.asyncio
async def test_changed_overlap_requires_revision(tmp_path):
    store = Store(tmp_path / 'db.sqlite')
    first = await replay(store, page('abcdef'))
    with pytest.raises(ValueError, match='CHANGED_WITHOUT_REVISION'):
        await replay(store, page('XXXX', 4))
    second = await replay(store, page('changed text', total=12, revision='r2'))
    assert first['source_ids'] != second['source_ids']


@pytest.mark.asyncio
async def test_pdf_handoff_does_not_register_unread_content(tmp_path):
    store = Store(tmp_path / 'db.sqlite')
    result = await replay(store, dict(document_type='pdf',
        retrieval_status='requires_pdf_reader',
        pdf_url='https://aclanthology.org/2024.findings-acl.212.pdf'), 'read_web')
    assert result['next_tool'] == 'read_paper' and not result['source_ids']
    assert not store.list_sources()


@pytest.mark.asyncio
async def test_nonarxiv_title_and_web_pages(tmp_path):
    store = Store(tmp_path / 'db.sqlite')
    body = page('# Research title', total=16)
    body['paper'] = {}
    result = await replay(store, body)
    assert result['sources'][0]['title'] == 'Research title'
    for start, text in [(0, 'abcdef'), (6, 'ghijkl')]:
        result = await replay(store, dict(text=text, offset=start, total_chars=12,
            resource_id='web1', version='v1', final_url='https://example.org/article',
            title='Page', next_offset=None if start else 6, eof=bool(start)),
            'read_web', {'url': 'https://example.org/article'})
    assert store.get_source(result['source_ids'][0]).content_complete


@pytest.mark.asyncio
async def test_paper_search_miss_is_not_registered_as_evidence(tmp_path):
    store = Store(tmp_path / 'db.sqlite')
    first = await replay(store, page('abcdef'))
    before = store.get_source(first['source_ids'][0]).model_dump()
    result = await replay(store, dict(status='success', match_status='no_match', no_match=True,
        document_id='paper1', document_revision='r1', markdown='', matches=[],
        range={'start': 0, 'end': 0}, search_range={'start': 0, 'end': 12},
        total_chars=12, coverage='no_text_returned', next_offset=None))
    assert not result['is_error'] and not result['source_ids']
    assert result['match_status'] == 'no_match'
    assert result['search_range'] == {'start': 0, 'end': 12}
    assert len(store.list_sources()) == 1
    assert store.get_source(first['source_ids'][0]).model_dump() == before
