import json
from decimal import Decimal
import pytest
from arc.runtime import build_tools
from arc.mcp_client import Capability
from arc.store import Store

class Hub:
    capabilities = {
        'read_paper': Capability('read_paper','scholaranalysis','get_paper_text',{},'original',Decimal(0),'LOCAL'),
        'read_web': Capability('read_web','webresearch','fetch_page',{},'original',Decimal(0),'LOCAL')}
    async def call(self, *args):raise AssertionError('No network in replay')

async def replay(store, body, name='read_paper', arguments=None):
    path='raw/current.json'
    store.save_artifact(path,json.dumps({'is_error':False,'structured_content':body,'content':[]}))
    return await build_tools(store,Hub())[name].handler(arguments or {},{'raw_response_artifact_path':path})

def page(text, start=0, total=12, revision='r1'):
    return dict(status='success',paper={'title':'Paper'},markdown=text,
        source={'final_url':'https://aclanthology.org/2024.findings-acl.212.pdf'},
        document_id='doc1',document_revision=revision,mode='text',
        range={'start':start,'end':start+len(text)},total_chars=total,
        next_offset=start+len(text) if start+len(text)<total else None,eof=start+len(text)==total)

@pytest.mark.asyncio
async def test_contiguous_pages_extend_one_source_and_history_survives(tmp_path):
    store=Store(tmp_path/'db.sqlite')
    first=await replay(store,page('abcdef'))
    original=store.get_source(first['source_ids'][0]);old_path=original.content_path
    second=await replay(store,page('ghijkl',6))
    assert second['source_ids']==first['source_ids']
    assert store.get_record(original.source_id)['content']=='abcdefghijkl'
    assert store.get_source(original.source_id).content_complete
    assert store.read_artifact(old_path)=='abcdef'
    again=await replay(store,page('abcdef'))
    assert again['sources'][0]['registered_content_complete']

@pytest.mark.asyncio
async def test_tail_is_partial_fragment_not_fabricated_fulltext(tmp_path):
    store=Store(tmp_path/'db.sqlite')
    result=await replay(store,page('ijkl',8))
    source=store.get_source(result['source_ids'][0])
    assert not source.content_complete and source.content_start_char==8
    assert source.content_total_chars==12
    assert result['eof'] and result['sources'][0]['locator_coordinates']=='relative_to_cached_content'
    assert store.get_record(source.source_id)['content']=='ijkl'
