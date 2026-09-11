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
