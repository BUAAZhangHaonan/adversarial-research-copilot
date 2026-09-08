import json
from decimal import Decimal

import pytest

from arc.mcp_client import Capability
from arc.runtime import build_tools
from arc.schemas import SourceRecord
from arc.store import Store


class OfflinePaperHub:
    capabilities = {'read_paper': Capability('read_paper', 'scholaranalysis',
        'get_paper_text', {}, 'original', Decimal(0), 'LOCAL_MINERU')}

    def __init__(self):
        self.calls = 0

    async def call(self, name, arguments):
        self.calls += 1
        raise AssertionError('Saved raw must recover without remote calls')


def saved_paper(store, paper, text):
    # Matches actual MCP structured result; fixture contains no private paper text.
    response = {'is_error': False, 'structured_content': {'result': json.dumps({
        'status': 'success', 'mode': 'text_only', 'paper': paper, 'markdown': text})}, 'content': []}
    path = 'tools/saved-paper.raw.json'
    store.save_artifact(path, json.dumps(response))
    return {'run_id': 'fixture', 'raw_response_artifact_path': path}


@pytest.mark.asyncio
@pytest.mark.parametrize('title', ['', '   '])
async def test_empty_title_fulltext_saved_raw_registers_independent_representation(tmp_path, title):
    store = Store(tmp_path / 'state.sqlite')
    web = store.register_source(SourceRecord(title='Known web title',
        url='https://arxiv.org/html/2401.00001v2', arxiv_id='2401.00001v2',
        source_type='paper', access_status='retrieved', content_origin='original',
        content_complete=False, content_total_chars=40000,
        representation_id='webresearch:trafilatura:fixture'), content='web prefix')
    original_path = web.content_path
    text = 'Synthetic paper body.\n' * 4000 + 'FINAL_PASSAGE'
    metadata = saved_paper(store, {'title': title, 'arxiv_id': '2401.00001',
        'versioned_id': '2401.00001v2', 'authors': [], 'abstract': ''}, text)
    hub = OfflinePaperHub()
    tools = build_tools(store, hub)
    result = await tools['read_paper'].handler({'query': '2401.00001'}, metadata)
    assert result['is_error'] is False and len(result['source_ids']) == 1
    paper = store.get_source(result['source_ids'][0])
    assert paper.title == 'arXiv 2401.00001v2'
    assert paper.source_id != web.source_id
    assert paper.representation_id == 'scholaranalysis:get_paper_text:markdown'
    assert paper.content_complete and paper.content_total_chars == len(text)
    assert result['sources'][0]['content_requires_read_record'] is True
    tail = await tools['read_record'].handler({'record_id': paper.source_id,
        'offset': len(text)-13, 'limit': 64000}, {})
    assert tail['content'] == 'FINAL_PASSAGE'
    assert tail['requires_source_fetch'] is False
    assert store.get_source(web.source_id).content_path == original_path
    assert store.get_record(web.source_id)['content'] == 'web prefix'
    assert store.read_artifact(original_path) == 'web prefix'
    replay = await tools['read_paper'].handler({'query': '2401.00001'}, metadata)
    assert replay['source_ids'] == result['source_ids']
    assert hub.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('paper,text', [
    ({'title': '', 'arxiv_id': '2401.00001'}, 'body'),
    ({'title': '', 'versioned_id': 'invented-v1'}, 'body'),
    ({'title': '', 'versioned_id': '2401.00001v2'}, ''),
    ({'title': 'Present title'}, 'body'),
])
async def test_unregistrable_paper_is_explicit_error_not_success_empty_sources(tmp_path, paper, text):
    store = Store(tmp_path / 'state.sqlite')
    metadata = saved_paper(store, paper, text)
    hub = OfflinePaperHub()
    result = await build_tools(store, hub)['read_paper'].handler({'query': 'fixture'}, metadata)
    assert result['is_error'] is True
    assert result['error'] == 'MCP_SOURCE_METADATA_INCOMPLETE'
    assert result['missing'] and result['raw_artifact_path'] == metadata['raw_response_artifact_path']
    assert store.list_sources() == [] and hub.calls == 0
