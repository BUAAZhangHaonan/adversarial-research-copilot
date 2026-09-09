"""Finite reread warning and pause with real Runtime checkpoints, no paid calls."""
import json
from decimal import Decimal

import pytest

from arc.discovery_validation import source_read_progress
from arc.runtime import BoundTool, RuntimePaused
from tests.test_discovery_validation import page, fetch
from tests.test_runtime import setup_runtime, invoke, sse, answer


def tool_reply(index, *, offset=0, limit=1000):
    return sse(finish='tool_calls',tools=[{'index':0,'id':f'read-{index}','type':'function',
        'function':{'name':'read_record','arguments':json.dumps({'record_id':'src_fixture',
            'offset':offset,'limit':limit})}}])


def reading_tool():
    async def read(arguments,metadata):
        content='x'*2000
        start=arguments['offset'];limit=arguments['limit']
        return {'source_id':'src_fixture','version':'1','representation_id':'fixture',
            'content':content[start:start+limit],'content_offset':start,
            'cached_content_chars':len(content),'content_total_chars':len(content),
            'content_complete':True}
    return BoundTool('read_record',{'type':'object','properties':{
        'record_id':{'type':'string'},'offset':{'type':'integer'},'limit':{'type':'integer'}},
        'required':['record_id','offset','limit'],'additionalProperties':False},read,Decimal(0),'LOCAL_CACHE_TEST')


def repeated_reads():
    return [tool_reply(0)]+[tool_reply(i,limit=1000-i*50) for i in range(1,9)]


def test_successful_prefix_rereads_changing_limit_do_not_count_as_new_material():
    trace=[page(length=100)]+[page(length=n) for n in range(99,91,-1)]
    result=source_read_progress(trace)
    assert result['consecutive_nonprogress_reads']==8 and not result['repeated_eof']
    assert source_read_progress(trace+[page(start=100,length=20)])['consecutive_nonprogress_reads']==0
    assert source_read_progress(trace+[fetch(content_origin='metadata',content_chars=0,source_id='new-metadata')])['consecutive_nonprogress_reads']==8
    assert source_read_progress(trace+[fetch(content_chars=300)])['consecutive_nonprogress_reads']==0
    assert source_read_progress(trace+[{'name':'read_record','result':{'is_error':True}}])['consecutive_nonprogress_reads']==8


@pytest.mark.asyncio
async def test_one_registered_warning_can_finish_without_scientific_rejection(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,repeated_reads()+[sse(json.dumps(answer()))],
                                               tools={'read_record':reading_tool()})
    try:
        result=await invoke(runtime,tool_profile=['read_record'])
        assert result.result.value=='valid' and len(requests)==10
        state=json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
        notice=state['source_read_progress_notice']
        assert notice['template']=='tasks/source_read_no_progress.md'
        assert notice['uses_original_task_snapshot']
        assert 'JSON' in notice['instruction'] and notice['source']
        assert sum(m.get('content')==notice['instruction'] for m in state['messages'])==1
        assert notice['diagnostics']['consecutive_nonprogress_reads']==8
        assert all(c['state']=='SETTLED' for c in ledger.list_calls())
    finally:await runtime.close()


@pytest.mark.asyncio
async def test_continued_reread_after_warning_pauses_before_buying_another_request(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,repeated_reads()+[tool_reply(9,limit=300)],
                                               tools={'read_record':reading_tool()})
    try:
        with pytest.raises(RuntimePaused,match='SOURCE_READ_NO_PROGRESS'):
            await invoke(runtime,tool_profile=['read_record'])
        assert len(requests)==10 and store.get_task('task_fixture').status=='PAUSED_EXTERNAL'
        assert store.get_task('task_fixture').accepted_result is None
        assert all(c['state']=='SETTLED' for c in ledger.list_calls())
        with pytest.raises(RuntimePaused,match='SOURCE_READ_NO_PROGRESS'):
            await invoke(runtime,tool_profile=['read_record'])
        assert len(requests)==10
    finally:await runtime.close()


@pytest.mark.asyncio
async def test_new_page_after_warning_can_continue_and_resume_keeps_one_notice(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,repeated_reads()+[
        tool_reply(9,offset=1000),sse(json.dumps(answer()))],tools={'read_record':reading_tool()})
    original_request=runtime._model_request
    interrupted=False
    async def interrupt_at_notice(record,state,*args):
        nonlocal interrupted
        if state.get('source_read_progress_notice') and not interrupted:
            interrupted=True
            raise SystemExit('Simulated stop after durable warning before another model call')
        return await original_request(record,state,*args)
    runtime._model_request=interrupt_at_notice
    try:
        with pytest.raises(SystemExit):await invoke(runtime,tool_profile=['read_record'])
        assert len(requests)==9
        assert (await invoke(runtime,tool_profile=['read_record'])).result.value=='valid'
        assert len(requests)==11
        state=json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
        notice=state['source_read_progress_notice']
        assert sum(m.get('content')==notice['instruction'] for m in state['messages'])==1
    finally:await runtime.close()


def test_new_notice_for_old_snapshot_is_registered_and_preserves_original_prompt(tmp_path):
    import copy
    import shutil
    from arc.prompting import PromptLoader
    from tests.test_runtime import ROOT
    old_root=tmp_path/'old-prompts'
    shutil.copytree(ROOT/'prompts',old_root)
    manifest=json.loads((old_root/'manifest.json').read_text())
    manifest.pop('read_progress_template')
    (old_root/'manifest.json').write_text(json.dumps(manifest))
    old=PromptLoader(old_root).render('investigator.INVOKE',
        {'task_id':'old','subject':{},'payload':{}},schema={},tool_profile=['read_record'])
    before=copy.deepcopy(old)
    notice=PromptLoader(ROOT/'prompts').render_read_progress(old,
        {'consecutive_nonprogress_reads':129,'trace_count':177})
    assert not notice['uses_original_task_snapshot']
    assert '129' in notice['instruction'] and notice['source']
    assert old==before
