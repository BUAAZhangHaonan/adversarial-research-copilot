import json
from decimal import Decimal
from pathlib import Path
import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict
from arc.budget import BudgetLedger
from arc.store import Store
from arc.prompting import PromptLoader
from arc.pricing import PriceBook
from arc.runtime import Runtime, RuntimePaused, BoundTool

ROOT=Path(__file__).parents[1]
SUBJECT={'campaign_id':None,'run_id':'run_fixture','card_id':None,'card_version':None}

class Result(BaseModel):
    model_config=ConfigDict(extra='forbid')
    value: str
    evidence_ids: list[str]

def answer(value='valid', evidence_ids=None):
    return {'schema_version':'arc.v1','task_id':'task_fixture','subject':SUBJECT,'result_status':'complete',
            'result':{'value':value,'evidence_ids':evidence_ids or []},'evidence_requests':[],
            'capability_requests':[],'note':None}

def sse(text=None, finish='stop', tools=None, reasoning='private reasoning', model='deepseek-v4-flash'):
    chunks=[{'id':'req_fixture','object':'chat.completion.chunk','created':1,'model':model,
             'choices':[{'index':0,'delta':{'role':'assistant','reasoning_content':reasoning},'finish_reason':None}]}]
    delta={'content':text} if tools is None else {'tool_calls':tools}
    chunks.append({'id':'req_fixture','object':'chat.completion.chunk','created':1,'model':model,
                   'choices':[{'index':0,'delta':delta,'finish_reason':None}]})
    if finish is not None:
        chunks.append({'id':'req_fixture','object':'chat.completion.chunk','created':1,'model':model,
            'choices':[{'index':0,'delta':{},'finish_reason':finish}],
            'usage':{'prompt_tokens':100,'completion_tokens':50,'total_tokens':150,
                     'prompt_cache_hit_tokens':20,'prompt_cache_miss_tokens':80,
                     'completion_tokens_details':{'reasoning_tokens':40}}})
    return ''.join('data: '+json.dumps(chunk)+'\n\n' for chunk in chunks)+'data: [DONE]\n\n'

def setup_runtime(tmp_path, responses, *, amount='20', tools=None):
    store=Store(tmp_path/'state.sqlite');store.create_run('discover',run_id=SUBJECT['run_id'])
    ledger=BudgetLedger(tmp_path/'state.sqlite');ledger.create_account('parent','100');ledger.create_account('stage',amount,parent_id='parent')
    requests=[]
    async def handle(request):
        requests.append(json.loads(request.content))
        body=responses.pop(0)
        if isinstance(body,Exception):raise body
        return httpx.Response(200,headers={'content-type':'text/event-stream'},content=body)
    client=AsyncOpenAI(api_key='offline-test-only',base_url='https://offline.invalid',max_retries=0,
                       http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    runtime=Runtime(store=store,ledger=ledger,account_id='stage',loader=PromptLoader(ROOT/'prompts'),
        role_models={'investigator':'deepseek-v4-flash'},prices=PriceBook(ROOT/'configs/pricing.json'),client=client,tools=tools)
    return runtime,store,ledger,requests

async def invoke(runtime, **kwargs):
    return await runtime.invoke('investigator','INVOKE',{'text':'a'*2000+'DECISIVE_END_CONDITION'},
                                Result,SUBJECT,'task_fixture',**kwargs)

@pytest.mark.asyncio
async def test_actual_sdk_request_max_full_output_usage_and_role_resume(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(answer()))])
    result=await invoke(runtime)
    assert result.result.value=='valid'
    sent=requests[0]
    assert sent['reasoning_effort']=='max' and sent['thinking']=={'type':'enabled'}
    assert sent['max_tokens']==384000 and sent['stream'] and sent['response_format']=={'type':'json_object'}
    assert 'DECISIVE_END_CONDITION' in sent['messages'][1]['content']
    assert 'temperature' not in sent and 'stop' not in sent
    before=ledger.summary('parent')
    assert Decimal(before['spent_upper_cny'])>0 and Decimal(before['reserved_cny'])==0
    assert (await invoke(runtime)).result.value=='valid'
    assert len(requests)==1 and ledger.summary('parent')==before
    assert store.get_task('task_fixture').status=='ACCEPTED'
    await runtime.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('finish',['length','content_filter','insufficient_system_resource'])
async def test_nonempty_invalid_finish_never_accepted_or_repaired(tmp_path,finish):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(answer()),finish=finish)])
    with pytest.raises(RuntimePaused) as caught:await invoke(runtime)
    assert caught.value.status=='PAUSED_PROTOCOL'
    assert store.get_task('task_fixture').accepted_result is None and len(requests)==1
    assert Decimal(ledger.summary('parent')['spent_upper_cny'])>0
    await runtime.close()

@pytest.mark.asyncio
async def test_single_structural_repair_and_original_failure_preserved(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse('{broken'),sse(json.dumps(answer('fixed')))])
    assert (await invoke(runtime)).result.value=='fixed'
    assert len(requests)==2 and all(r['reasoning_effort']=='max' for r in requests)
    assert 'Repair an invalid structured response' in requests[1]['messages'][1]['content']
    assert len(ledger.list_calls())==2
    await runtime.close()

@pytest.mark.asyncio
async def test_second_bad_structure_stops_with_two_attempts(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse('{}'),sse('{}')])
    with pytest.raises(RuntimePaused,match='INVALID_OUTPUT_AFTER_REPAIR'):await invoke(runtime)
    assert len(requests)==2 and store.get_task('task_fixture').status=='PAUSED_PROTOCOL'
    await runtime.close()

@pytest.mark.asyncio
async def test_budget_admission_precedes_draw_callback_and_no_dynamic_shortening(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[],amount='.01')
    admission=[]
    with pytest.raises(RuntimePaused) as caught:await invoke(runtime,on_admitted=lambda:admission.append(1))
    assert caught.value.status=='PAUSED_BUDGET' and not admission and not requests
    await runtime.close()

@pytest.mark.asyncio
async def test_disconnect_unknown_keeps_reservation_and_no_replay(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse('unfinished',finish=None)])
    with pytest.raises(RuntimePaused):await invoke(runtime)
    assert Decimal(ledger.summary('parent')['reserved_cny'])>0
    with pytest.raises(RuntimePaused,match='REMOTE_RESULT_UNKNOWN'):await invoke(runtime)
    assert len(requests)==1 and store.get_task('task_fixture').status=='UNKNOWN'
    await runtime.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('model',['deepseek-v4-flash','deepseek-v4-pro'])
async def test_native_tool_reasoning_association_and_trace(tmp_path,model):
    calls=[]
    async def read(args,meta):calls.append((args,meta));return {'source_ids':[],'answer':'fixture-data'}
    tool=BoundTool('read_record',{'type':'object','properties':{'record_id':{'type':'string'}},'required':['record_id']},read,Decimal(0),'LOCAL')
    tool_parts=[{'index':0,'id':'provider_tool_1','type':'function','function':{'name':'read_record','arguments':'{"record_id":"record_1"}'}}]
    second_parts=[{'index':0,'id':'provider_tool_2','type':'function','function':{'name':'read_record','arguments':'{"record_id":"record_2"}'}}]
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(finish='tool_calls',tools=tool_parts,reasoning='reasoning 1',model=model),sse(finish='tool_calls',tools=second_parts,reasoning='reasoning 2',model=model),sse(json.dumps(answer()),model=model)],tools={'read_record':tool})
    runtime.role_models['investigator']=model
    assert (await invoke(runtime,tool_profile=['read_record'])).result.value=='valid'
    assert len(calls)==2 and len(requests)==3
    for sent in requests:
        assert sent['model']==model and sent['thinking']=={'type':'enabled'} and sent['reasoning_effort']=='max'
        assert sent['max_tokens']==384000 and sent['stream'] and sent['stream_options']=={'include_usage':True}
        assert sent['response_format']=={'type':'json_object'} and sent['tools']==requests[0]['tools']
        assert 'tool_choice' not in sent and 'temperature' not in sent and 'stop' not in sent
    for number in (1,2):
        assistant=requests[number]['messages'][-2];reply=requests[number]['messages'][-1]
        assert assistant['reasoning_content']==f'reasoning {number}'
        assert assistant['tool_calls'][0]['id']==reply['tool_call_id']==f'provider_tool_{number}'
    assert requests[2]['messages'][:-2]==requests[1]['messages']
    assert all(trace['status']=='completed' and trace['name']=='read_record' for trace in runtime.tool_trace('task_fixture'))
    assert len(ledger.list_calls())==5
    cost=ledger.summary('parent')
    assert (await invoke(runtime,tool_profile=['read_record'])).result.value=='valid'
    assert len(requests)==3 and len(calls)==2 and ledger.summary('parent')==cost
    await runtime.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('invalid_content',['', 'A prose response instead of JSON.'])
@pytest.mark.parametrize('repair_succeeds',[True,False])
async def test_native_json_output_invalid_or_empty_keeps_single_repair_policy(tmp_path,invalid_content,repair_succeeds):
    calls=[]
    async def read(args,meta):
        calls.append(args);return {'source_ids':[],'answer':'fixture-data'}
    tool=BoundTool('read_record',{'type':'object','properties':{'record_id':{'type':'string'}},'required':['record_id']},read,Decimal(0),'LOCAL')
    parts=[{'index':0,'id':'provider_tool_1','type':'function','function':{'name':'read_record','arguments':'{"record_id":"record_1"}'}}]
    repaired=json.dumps(answer('fixed')) if repair_succeeds else invalid_content
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(finish='tool_calls',tools=parts),sse(invalid_content),sse(repaired)],tools={'read_record':tool})
    if repair_succeeds:
        assert (await invoke(runtime,tool_profile=['read_record'])).result.value=='fixed'
    else:
        with pytest.raises(RuntimePaused,match='INVALID_OUTPUT_AFTER_REPAIR'):
            await invoke(runtime,tool_profile=['read_record'])
        assert store.get_task('task_fixture').accepted_result is None
        with pytest.raises(RuntimePaused,match='INVALID_OUTPUT_AFTER_REPAIR'):
            await invoke(runtime,tool_profile=['read_record'])
    assert len(requests)==3 and len(calls)==1 and len(ledger.list_calls())==4
    assert all(r['response_format']=={'type':'json_object'} and r['max_tokens']==384000
        and r['reasoning_effort']=='max' and r['thinking']=={'type':'enabled'} and r['stream']
        and 'tool_choice' not in r for r in requests)
    assert requests[0]['tools']==requests[1]['tools'] and 'tools' not in requests[2]
    assert 'Repair an invalid structured response' in requests[2]['messages'][1]['content']
    state=json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
    assert state['repair_count']==1
    await runtime.close()

@pytest.mark.asyncio
async def test_reference_hallucination_still_rejected_after_one_correction(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(answer(evidence_ids=['made_up']))),
        sse(json.dumps(answer(evidence_ids=['made_up'])))])
    with pytest.raises(RuntimePaused,match='INVALID_OUTPUT_AFTER_REPAIR'):await invoke(runtime)
    assert len(requests)==2 and store.get_task('task_fixture').accepted_result is None
    await runtime.close()

@pytest.mark.asyncio
async def test_repair_cannot_invent_reference(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse('{}'),sse(json.dumps(answer(evidence_ids=['invented'])))])
    with pytest.raises(RuntimePaused,match='INVALID_OUTPUT_AFTER_REPAIR'):await invoke(runtime)
    assert len(requests)==2 and store.get_task('task_fixture').accepted_result is None
    await runtime.close()


@pytest.mark.asyncio
async def test_response_saved_before_validation_recovers_locally_after_long_pause(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(answer()))])
    validate=runtime._validate_semantics
    def crash(*args):raise SystemExit('simulated process loss after durable response')
    runtime._validate_semantics=crash
    with pytest.raises(SystemExit):await invoke(runtime)
    task=store.get_task('task_fixture')
    assert task.status=='RESPONSE_SAVED'
    task.created_at='2020-01-01T00:00:00+00:00';store.put_task(task)
    runtime._validate_semantics=validate
    def no_live_render(*args,**kwargs):raise AssertionError('resumption reloaded live prompt')
    runtime.loader.render=no_live_render
    assert (await invoke(runtime)).result.value=='valid'
    assert len(requests)==1 and len(ledger.list_calls())==1
    await runtime.close()


@pytest.mark.asyncio
async def test_successful_tool_reused_after_next_request_budget_pause(tmp_path):
    holder={};tool_calls=[]
    async def read(args,meta):
        tool_calls.append(args)
        holder['ledger'].reserve('stage','hold','19')
        return {'source_ids':[],'answer':'retained-tool-result'}
    tool=BoundTool('read_record',{'type':'object','properties':{'record_id':{'type':'string'}},'required':['record_id']},read,Decimal(0),'LOCAL')
    parts=[{'index':0,'id':'tool_1','type':'function','function':{'name':'read_record','arguments':'{"record_id":"record_1"}'}}]
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(finish='tool_calls',tools=parts),sse(json.dumps(answer()))],tools={'read_record':tool})
    holder['ledger']=ledger
    with pytest.raises(RuntimePaused) as paused:await invoke(runtime,tool_profile=['read_record'])
    assert paused.value.status=='PAUSED_BUDGET' and len(tool_calls)==1 and len(requests)==1
    ledger.mark_not_sent('hold')
    assert (await invoke(runtime,tool_profile=['read_record'])).result.value=='valid'
    assert len(tool_calls)==1 and len(requests)==2
    assert 'retained-tool-result' in requests[-1]['messages'][-1]['content']
    await runtime.close()


@pytest.mark.asyncio
async def test_changed_payload_requires_explicit_fork_without_paid_call(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(answer()))])
    await invoke(runtime)
    with pytest.raises(RuntimePaused,match='FORK_REQUIRED'):
        await runtime.invoke('investigator','INVOKE',{'text':'different'},Result,SUBJECT,'task_fixture')
    assert len(requests)==1
    await runtime.close()


@pytest.mark.asyncio
async def test_saved_response_settles_with_original_price_snapshot_after_restart(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(answer()))])
    settle=runtime._settle_response
    async def crash(*args):raise SystemExit('process loss before settlement')
    runtime._settle_response=crash
    with pytest.raises(SystemExit):await invoke(runtime)
    response=json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))['response']
    old_book=runtime.prices
    replacement=json.loads(old_book.raw)
    replacement['snapshot_id']='later-prices'
    for period in replacement['models']['deepseek-v4-flash']['prices'].values():
        period.update(hit='100',miss='1000',output='2000')
    runtime.prices=PriceBook.from_bytes(json.dumps(replacement).encode())
    runtime._settle_response=settle
    assert (await invoke(runtime)).result.value=='valid'
    call=ledger.get_call(response['call_id'])
    assert Decimal(call['upper_micro'])/1000000 < Decimal('.001')
    assert len(requests)==1
    await runtime.close()


@pytest.mark.asyncio
async def test_resume_keeps_original_tool_description(tmp_path):
    async def read(args,meta):return {'source_ids':[]}
    tool=BoundTool('read_record',{'type':'object','properties':{}},read,Decimal(0),'LOCAL')
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(answer()))],tools={'read_record':tool})
    await invoke(runtime,tool_profile=['read_record'])
    runtime.loader.tool_description=lambda *args:'changed live description'
    assert (await invoke(runtime,tool_profile=['read_record'])).result.value=='valid'
    assert len(requests)==1
    await runtime.close()


@pytest.mark.asyncio
async def test_actual_searches_must_cover_successful_search_trace(tmp_path):
    from arc.schemas import Envelope, SearchTrace
    from arc.store import StateError
    class Searches(BaseModel):
        actual_searches: list[SearchTrace]
    runtime,store,ledger,requests=setup_runtime(tmp_path,[])
    raw=answer();raw['result']={'actual_searches':[]}
    state={'tool_trace':[{'call_id':'trace_1','status':'completed','name':'search_web',
                         'arguments':{'query':'fixture query'},'source_ids':[]}]}
    with pytest.raises(StateError,match='actual_searches_incomplete'):
        runtime._validate_semantics(Envelope[Searches].model_validate(raw),{},state)
    raw['result']['actual_searches']=[{'trace_id':'trace_1','operation':'search_web','query':'fixture query','source_ids':[]}]
    runtime._validate_semantics(Envelope[Searches].model_validate(raw),{},state)
    raw['result']['actual_searches'][0]['query']='invented query'
    with pytest.raises(StateError,match='actual_search_trace_mismatch'):
        runtime._validate_semantics(Envelope[Searches].model_validate(raw),{},state)
    await runtime.close()


@pytest.mark.asyncio
async def test_service_adapter_registers_original_without_truncating_paper(tmp_path):
    from arc.runtime import build_tools
    from arc.mcp_client import Capability
    text='original paper line\n'*1000+'DECISIVE_FINAL_SENTENCE'
    class Hub:
        capabilities={'read_paper':Capability('read_paper','scholaranalysis','get_paper_text',{},'original',Decimal(0),'LOCAL_MINERU')}
        async def call(self,name,args):
            return {'is_error':False,'structured_content':{'result':json.dumps({'status':'success',
                'paper':{'title':'Paper fixture','arxiv_id':'2401.00001','versioned_id':'2401.00001v2'},'markdown':text})},'content':[]}
    store=Store(tmp_path/'state.sqlite');store.create_run('discover',run_id=SUBJECT['run_id'])
    tools=build_tools(store,Hub())
    result=await tools['read_paper'].handler({'query':'2401.00001v2'},
        {'run_id':SUBJECT['run_id'],'raw_response_artifact_path':'tools/paper.raw.json'})
    assert not result['is_error'] and len(result['source_ids'])==1
    source=store.get_source(result['source_ids'][0])
    assert source.source_type=='paper' and source.content_origin=='original' and source.access_status=='retrieved'
    assert store.get_record(source.source_id)['content']==text
    assert result['sources'][0]['content'] is None and result['sources'][0]['content_requires_read_record']
    excerpt=await tools['read_record'].handler({'record_id':source.source_id,'offset':len(text)-30,'limit':30},{})
    assert excerpt['content'].endswith('DECISIVE_FINAL_SENTENCE') and not excerpt['more_cached_content']
    assert excerpt['content_complete'] and not excerpt['requires_source_fetch']
    assert excerpt['content_total_chars']==source.content_total_chars
    assert excerpt['cached_content_chars']==len(text)


@pytest.mark.asyncio
@pytest.mark.parametrize('offset,limit,more_cached,fetch', [(0,24000,True,False), (68000,24000,False,True), (90000,1000,False,True)])
async def test_partial_source_cache_end_preserves_original_coverage(tmp_path,offset,limit,more_cached,fetch):
    from arc.runtime import build_tools
    from arc.schemas import SourceRecord
    store=Store(tmp_path/'state.sqlite')
    tail='TRUNCATED_EQUATION___'
    text='x'*(90000-len(tail))+tail
    assert len(text)==90000
    source=store.register_source(SourceRecord(title='Partial original fixture',url='https://example.org/paper',
        source_type='paper',access_status='retrieved',content_origin='original',
        content_complete=False,content_total_chars=124840),text)
    before=store.get_source(source.source_id).model_dump(mode='json')
    result=await build_tools(store)['read_record'].handler({'record_id':source.source_id,'offset':offset,'limit':limit},{})
    assert result['content']==text[offset:offset+limit]
    assert result['content_total_chars']==124840 and result['content_complete'] is False
    assert result['cached_content_chars']==90000 and result['content_offset']==offset
    assert result['more_cached_content'] is more_cached and result['requires_source_fetch'] is fetch
    assert 'more_content' not in result
    assert store.get_source(source.source_id).model_dump(mode='json')==before


@pytest.mark.asyncio
async def test_unknown_original_length_is_not_replaced_with_cache_length(tmp_path):
    from arc.runtime import build_tools
    from arc.schemas import SourceRecord
    store=Store(tmp_path/'state.sqlite')
    source=store.register_source(SourceRecord(title='Unknown total fixture',url='https://example.org/unknown',
        source_type='paper',access_status='retrieved',content_origin='original',
        content_complete=False,content_total_chars=None),'partial')
    result=await build_tools(store)['read_record'].handler({'record_id':source.source_id},{})
    assert result['content_total_chars'] is None and result['cached_content_chars']==7
    assert result['requires_source_fetch'] and not result['more_cached_content']


@pytest.mark.asyncio
async def test_metadata_only_source_reads_expose_missing_body_without_claiming_completeness(tmp_path):
    from arc.runtime import build_tools
    from arc.schemas import SourceRecord
    store=Store(tmp_path/'state.sqlite')
    # Reproduce old metadata records which incorrectly defaulted to complete.
    source=store.register_source(SourceRecord(title='Metadata fixture',url='https://example.org/metadata',
        source_type='paper',access_status='metadata_only',content_origin='metadata',content_complete=True))
    before=store.get_source(source.source_id).model_dump(mode='json')
    tool=build_tools(store)['read_record']
    for offset in (0,3000):
        result=await tool.handler({'record_id':source.source_id,'offset':offset,'limit':3000},{})
        assert result['content'] is None and result['content_complete'] is False
        assert result['content_total_chars'] is None and result['cached_content_chars']==0
        assert result['requires_source_fetch'] and not result['more_cached_content']
        assert result['content_origin']=='metadata' and result['access_status']=='metadata_only'
    assert store.get_source(source.source_id).model_dump(mode='json')==before


@pytest.mark.asyncio
async def test_service_search_snippet_stays_metadata(tmp_path):
    from arc.runtime import build_tools
    from arc.mcp_client import Capability
    class Hub:
        capabilities={'search_web':Capability('search_web','webresearch','web_search',{},'metadata',Decimal(0),'DETERMINISTIC')}
        async def call(self,name,args):
            return {'is_error':False,'structured_content':{'results':[{'url':'https://example.org/paper',
                'title':'Search hit','snippet':'search excerpt is not original full text'}]},'content':[]}
    store=Store(tmp_path/'state.sqlite');store.create_run('discover',run_id=SUBJECT['run_id'])
    result=await build_tools(store,Hub())['search_web'].handler({'query':'query'},
        {'run_id':SUBJECT['run_id'],'raw_response_artifact_path':'tools/search.raw.json'})
    source=store.get_source(result['source_ids'][0])
    assert source.content_origin=='metadata' and source.access_status=='metadata_only'
    assert source.content_path is None and source.source_type=='web_unclassified'
    assert source.content_complete is False and source.content_total_chars is None


@pytest.mark.asyncio
async def test_reserved_orphan_before_task_checkpoint_released_on_resume(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(answer()))])
    reserve=ledger.reserve
    def crash(*args,**kwargs):
        reserve(*args,**kwargs)
        raise SystemExit('process lost after durable reservation before task checkpoint')
    ledger.reserve=crash
    with pytest.raises(SystemExit):await invoke(runtime)
    assert ledger.list_calls()[0]['state']=='RESERVED' and not requests
    ledger.reserve=reserve
    assert (await invoke(runtime)).result.value=='valid'
    assert len(requests)==1 and len(ledger.list_calls())==2
    assert ledger.list_calls()[0]['state']=='NOT_SENT'
    assert Decimal(ledger.summary('parent')['reserved_cny'])==0
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('visibility', ['absent', 'payload', 'tool_trace'])
async def test_new_evidence_reference_requires_task_visibility_even_when_registered(tmp_path, visibility):
    from arc.schemas import Envelope, SourceRecord, EvidenceRecord
    from arc.store import StateError
    class ReopeningResult(BaseModel):
        new_evidence_ids: list[str]
    runtime,store,ledger,requests=setup_runtime(tmp_path,[])
    source=store.register_source(SourceRecord(title='Original fixture',url='https://example.org/fixture',
        source_type='paper',access_status='retrieved',content_origin='original'),content='A controlled observation.')
    evidence=store.register_evidence(EvidenceRecord(source_id=source.source_id,claim_id='claim_fixture',
        claim_version=1,claim='A controlled observation.',conditions=['fixture condition'],locator='L1',
        excerpt='A controlled observation.',relation='motivates',origin='original',locator_status='verified',
        verification_status='verified',support_explanation='The passage contains this observation.'))
    raw=answer();raw['result']={'new_evidence_ids':[evidence.evidence_id]}
    envelope=Envelope[ReopeningResult].model_validate(raw)
    payload={'new_evidence_ids':[evidence.evidence_id]} if visibility=='payload' else {}
    trace={'call_id':'read_fixture','status':'completed','name':'read_record','arguments':{},
           'source_ids':[],'evidence_ids':[evidence.evidence_id]}
    state={'tool_trace':[trace] if visibility=='tool_trace' else []}
    if visibility=='absent':
        with pytest.raises(StateError,match='reference_not_supplied_to_task'):
            runtime._validate_semantics(envelope,payload,state)
    else:
        runtime._validate_semantics(envelope,payload,state)
    assert not requests
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['task_id', 'subject'])
async def test_wrong_task_or_subject_is_semantic_failure_without_repair(tmp_path,field):
    raw=answer()
    if field=='task_id':raw['task_id']='another_task'
    else:raw['subject']={**SUBJECT,'card_id':'another_card','card_version':1}
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(raw)),sse(json.dumps(answer()))])
    with pytest.raises(RuntimePaused,match='SUBJECT_OR_TASK_MISMATCH'):
        await invoke(runtime)
    assert len(requests)==1 and len(ledger.list_calls())==1
    assert store.get_task('task_fixture').status=='PAUSED_PROTOCOL'
    assert store.get_task('task_fixture').accepted_result is None
    await runtime.close()


@pytest.mark.asyncio
async def test_web_excerpt_then_full_read_upgrades_same_original_without_protocol_marker(tmp_path):
    from arc.runtime import build_tools
    from arc.mcp_client import Capability
    body={'url':'https://arxiv.org/html/2112.01527v1','title':'Paper','extractor':'trafilatura',
          'resource':{'content_hash':'same-html-hash','extractor':'trafilatura'}}
    class Hub:
        capabilities={'read_web':Capability('read_web','webresearch','fetch_page',{},'original',Decimal(0),'HTTP_FETCH')}
        async def call(self,name,args):
            text='abcdefghijk'
            if args['max_chars']<len(text):text=text[:args['max_chars']]+'\n...[truncated 11 chars]'
            return {'is_error':False,'structured_content':{**body,'text':text},'content':[]}
    store=Store(tmp_path/'state.sqlite')
    tool=build_tools(store,Hub())['read_web']
    short=await tool.handler({'url':body['url'],'max_chars':7},
        {'run_id':SUBJECT['run_id'],'raw_response_artifact_path':'tools/short.raw.json'})
    original=store.get_source(short['source_ids'][0]);old_path=original.content_path
    assert not original.content_complete and original.content_total_chars==11
    assert store.read_artifact(old_path)=='abcdefg'
    complete=await tool.handler({'url':body['url'],'max_chars':20},
        {'run_id':SUBJECT['run_id'],'raw_response_artifact_path':'tools/full.raw.json'})
    assert complete['source_ids']==short['source_ids']
    source=store.get_source(short['source_ids'][0])
    assert source.content_complete and store.get_record(source.source_id)['content']=='abcdefghijk'
    assert store.read_artifact(old_path)=='abcdefg'
    reread=await tool.handler({'url':body['url'],'max_chars':7},
        {'run_id':SUBJECT['run_id'],'raw_response_artifact_path':'tools/short-again.raw.json'})
    assert reread['source_ids']==complete['source_ids']
    assert reread['sources'][0]['content']=='abcdefg'
    assert reread['sources'][0]['content_complete'] is False
    assert reread['sources'][0]['registered_content_complete'] is True
    assert store.get_record(source.source_id)['content']=='abcdefghijk'
    assert reread['sources'][0]['canonical_id']=='arxiv:2112.01527'
    assert reread['sources'][0]['version']=='1'
    assert reread['sources'][0]['representation_id']=='webresearch:trafilatura:same-html-hash'


@pytest.mark.asyncio
async def test_saved_mcp_response_recovers_local_registry_failure_without_remote_replay(tmp_path):
    from arc.runtime import build_tools
    from arc.mcp_client import Capability
    from arc.store import StateError
    remote=[]
    class Hub:
        capabilities={'read_web':Capability('read_web','webresearch','fetch_page',
            {'type':'object','properties':{'url':{'type':'string'}},'required':['url']},'original',Decimal(0),'HTTP_FETCH')}
        async def call(self,name,args):
            remote.append(args)
            return {'is_error':False,'structured_content':{'url':args['url'],'title':'Fetched original',
                'text':'Complete source passage.'},'content':[]}
    parts=[{'index':0,'id':'provider_read','type':'function','function':{'name':'read_web',
             'arguments':json.dumps({'url':'https://example.org/source'})}}]
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(finish='tool_calls',tools=parts),sse(json.dumps(answer()))])
    runtime.tools=build_tools(store,Hub())
    register=store.register_source
    def fail(*args,**kwargs):raise StateError('simulated_local_registry_failure')
    store.register_source=fail
    with pytest.raises(RuntimePaused,match='TOOL_LOCAL_PROCESSING_FAILED'):
        await invoke(runtime,tool_profile=['read_web'])
    task=store.get_task('task_fixture');state=json.loads(store.read_artifact(task.response_artifact_path))
    tool_call=ledger.get_call(state['pending_tool'])
    assert task.status=='PAUSED_PROTOCOL' and tool_call['state']=='SETTLED'
    assert tool_call['upper_micro']==0 and len(remote)==1
    assert json.loads(store.read_artifact(tool_call['metadata']['raw_response_artifact_path']))['is_error'] is False
    store.register_source=register
    assert (await invoke(runtime,tool_profile=['read_web'])).result.value=='valid'
    assert len(remote)==1 and len(requests)==2 and len(ledger.list_calls())==3
    trace=runtime.tool_trace('task_fixture')[0]
    assert trace['call_id']==tool_call['call_id'] and trace['status']=='completed'
    final=json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
    assert final['tool_processing_errors'][0]['error']=='simulated_local_registry_failure'
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('target', [('claim_current',1),('claim_current',2),('claim_foreign',1),(None,None)])
async def test_finding_target_is_exactly_visible_claim_version(tmp_path,target):
    from arc.schemas import Envelope,Finding,SourceRecord
    from arc.store import StateError
    class Findings(BaseModel):
        findings:list[Finding]
        contrary_findings:list[Finding]
    runtime,store,ledger,requests=setup_runtime(tmp_path,[])
    source=store.register_source(SourceRecord(title='Fixture source',url='https://example.org/metadata',
        source_type='paper',access_status='metadata_only',content_origin='metadata'))
    finding={'claim':'Observation','conditions':[],'source_id':source.source_id,'locator':None,
        'locator_status':'locator_unverified','relation':'motivates','origin':'inference','excerpt':None,
        'support_explanation':'Unverified metadata suggestion.','claim_id':target[0],'claim_version':target[1]}
    raw=answer();raw['result']={'findings':[finding],'contrary_findings':[]}
    payload={'claims':[{'claim_id':'claim_current','version':1}], 'source_ids':[source.source_id]}
    if target in [('claim_current',1),(None,None)]:
        runtime._validate_semantics(Envelope[Findings].model_validate(raw),payload,{'tool_trace':[]})
    else:
        with pytest.raises(StateError,match='finding_target_claim_not_supplied_to_task'):
            runtime._validate_semantics(Envelope[Findings].model_validate(raw),payload,{'tool_trace':[]})
    await runtime.close()


def request_answer(**targets):
    raw=answer()
    raw['evidence_requests']=[{'request_local_id':'request1','claim_id':None,'issue_id':None,
        'draw_id':None,'question':'Which original observation answers this question?',
        'target_source_ids':[],'queries':['specific original comparison'],
        'purpose':'Resolve the stated evidence gap.','decision_if_supported':'Retain this basis.',
        'decision_if_contradicted':'Record the contrary condition.',**targets}]
    return raw


@pytest.mark.asyncio
@pytest.mark.parametrize('field',['claim_id','issue_id','draw_id'])
@pytest.mark.parametrize('visible',[True,False])
async def test_evidence_request_entity_must_be_visible_in_frozen_payload(tmp_path,field,visible):
    from arc.schemas import Envelope
    from arc.store import StateError
    runtime,store,ledger,requests=setup_runtime(tmp_path,[])
    raw=request_answer(**{field:'current_entity' if visible else 'invented_entity'})
    payload={'nested_context':{'entities':[{field:'current_entity'}]}}
    envelope=Envelope[Result].model_validate(raw)
    if visible:
        runtime._validate_semantics(envelope,payload,{'tool_trace':[]})
    else:
        with pytest.raises(StateError,match=f'evidence_request_{field}_not_supplied_to_task'):
            runtime._validate_semantics(envelope,payload,{'tool_trace':[]})
    assert requests==[] and store.list_tasks(SUBJECT['run_id'])==[]
    await runtime.close()


@pytest.mark.asyncio
async def test_evidence_request_checks_each_target_and_never_uses_tool_or_other_entity_ids(tmp_path):
    from arc.schemas import Envelope
    from arc.store import StateError
    runtime,store,ledger,requests=setup_runtime(tmp_path,[])
    raw=request_answer(claim_id='claim1',issue_id='issue1',draw_id='draw1')
    payload={'claim_ids':['claim1'],'nested':{'issue_ids':['issue1'],'draw_ids':['draw1']}}
    envelope=Envelope[Result].model_validate(raw)
    runtime._validate_semantics(envelope,payload,{'tool_trace':[]})
    payload['nested'].pop('issue_ids')
    # Neither a claim with the same spelling nor a tool-returned issue grants
    # that issue membership in the task's frozen research input.
    payload['claim_ids'].append('issue1')
    trace={'call_id':'tool1','name':'read_record','status':'completed','issue_ids':['issue1']}
    with pytest.raises(StateError,match='evidence_request_issue_id_not_supplied_to_task'):
        runtime._validate_semantics(envelope,payload,{'tool_trace':[trace]})
    assert requests==[]
    await runtime.close()


@pytest.mark.asyncio
async def test_pre_card_null_evidence_request_targets_use_envelope_context(tmp_path):
    from arc.schemas import Envelope
    runtime,store,ledger,requests=setup_runtime(tmp_path,[])
    raw=request_answer()
    raw['subject']={**SUBJECT,'campaign_id':'campaign_fixture'}
    envelope=Envelope[Result].model_validate(raw)
    runtime._validate_semantics(envelope,{}, {'tool_trace':[]})
    assert envelope.evidence_requests[0].claim_id is None
    assert envelope.evidence_requests[0].issue_id is None
    assert envelope.evidence_requests[0].draw_id is None
    assert requests==[]
    await runtime.close()


@pytest.mark.asyncio
async def test_nested_existing_input_evidence_manifest_and_actual_dependency_snapshot(tmp_path):
    from arc.schemas import SourceRecord,EvidenceRecord
    from importlib.metadata import version
    import platform
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(answer()))])
    source=store.register_source(SourceRecord(title='Metadata fixture',url='https://example.org/fixture',
        source_type='paper',access_status='metadata_only',content_origin='metadata'))
    evidence=[]
    for index in range(3):
        evidence.append(store.register_evidence(EvidenceRecord(evidence_id=f'ev_fixture_{index}',
            source_id=source.source_id,claim_id=f'claim_{index}',claim_version=1,claim='Unverified suggestion',
            conditions=[],locator=None,excerpt=None,relation='motivates',origin='inference',
            locator_status='locator_unverified',verification_status='unverified',support_explanation='Metadata only.')))
    payload={'context':{'evidence':[evidence[0].model_dump(mode='json')],
                        'issues':[{'basis_evidence_ids':[evidence[1].evidence_id]}]}}
    await runtime.invoke('investigator','INVOKE',payload,Result,SUBJECT,'task_fixture')
    task=store.get_task('task_fixture')
    assert task.evidence_ids==[evidence[0].evidence_id,evidence[1].evidence_id]
    environment=json.loads(store.read_artifact(task.environment_snapshot_path))
    assert environment['python']==platform.python_version()
    assert environment['packages']['openai']==version('openai')
    assert environment['packages']['mcp']==version('mcp')
    assert ledger.list_calls()[0]['metadata']['environment_snapshot_hash']==task.environment_snapshot_hash
    assert evidence[2].evidence_id not in task.evidence_ids
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('target', ['prompt_messages','prompt_source','state_prefix','environment','repair_messages'])
async def test_corrupt_snapshot_refuses_resume_without_new_model_request(tmp_path,target):
    responses=[sse('{}'),sse(json.dumps(answer()))] if target=='repair_messages' else [sse(json.dumps(answer()))]
    runtime,store,ledger,requests=setup_runtime(tmp_path,responses)
    await invoke(runtime)
    before=len(requests)
    task=store.get_task('task_fixture')
    state=json.loads(store.read_artifact(task.response_artifact_path))
    if target in {'prompt_messages','prompt_source'}:
        path=task.rendered_prompt_path
        saved=json.loads(store.read_artifact(path))
        if target=='prompt_messages':saved['messages'][0]['content']+=' CORRUPTED'
        else:saved['sources'][next(iter(saved['sources']))]+=' CORRUPTED'
    elif target=='environment':
        path=task.environment_snapshot_path;saved=json.loads(store.read_artifact(path));saved['python']='changed'
    elif target=='repair_messages':
        path=state['repair_snapshot_path'];saved=json.loads(store.read_artifact(path));saved['messages'][0]['content']+=' CORRUPTED'
    else:
        path=task.response_artifact_path;saved=state;saved['messages'][0]['content']+=' CORRUPTED'
    store.save_artifact(path,json.dumps(saved,ensure_ascii=False))
    with pytest.raises(RuntimePaused) as paused:await invoke(runtime)
    assert paused.value.status=='PAUSED_PROTOCOL' and len(requests)==before
    assert len(ledger.list_calls())==before
    await runtime.close()


@pytest.mark.asyncio
async def test_changed_sdk_environment_requires_explicit_fork(tmp_path,monkeypatch):
    import arc.runtime as runtime_module
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(answer()))])
    await invoke(runtime)
    changed=runtime_module.environment_snapshot();changed['packages']['openai']='different-sdk-version'
    monkeypatch.setattr(runtime_module,'environment_snapshot',lambda:changed)
    with pytest.raises(RuntimePaused,match='DEPENDENCY_ENVIRONMENT_CHANGED_FORK_REQUIRED'):
        await invoke(runtime)
    assert len(requests)==1
    await runtime.close()


@pytest.mark.asyncio
async def test_unknown_nested_input_evidence_rejected_before_model_admission(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[])
    with pytest.raises(RuntimePaused,match='unknown_evidence_id'):
        await runtime.invoke('investigator','INVOKE',{'nested':{'new_evidence_ids':['not_registered']}},
            Result,SUBJECT,'task_fixture')
    assert not requests and not ledger.list_calls()
    await runtime.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('exists', [True, False])
async def test_local_record_read_returns_campaign_or_explicit_missing_error(tmp_path, exists):
    from arc.runtime import build_tools
    runtime,store,ledger,requests=setup_runtime(tmp_path,[])
    campaign=store.create_campaign('Current controlled question')
    tool=build_tools(store)['read_record']
    result=await tool.handler({'record_id':campaign.campaign_id if exists else 'not_registered'}, {'run_id':SUBJECT['run_id']})
    if exists:
        assert result['campaign_id']==campaign.campaign_id and result['topic']==campaign.topic
    else:
        assert result['is_error'] is True and result['error']=='record_missing'
    assert not requests and not ledger.list_calls()
    await runtime.close()


@pytest.mark.asyncio
async def test_local_read_processing_failure_resumes_without_new_tool_admission(tmp_path):
    from arc.runtime import build_tools
    from arc.store import StateError
    parts=[{'index':0,'id':'local_read','type':'function','function':{'name':'read_record',
             'arguments':json.dumps({'record_id':'not_registered'})}}]
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(finish='tool_calls',tools=parts),sse(json.dumps(answer()))])
    runtime.tools=build_tools(store)
    original=store.get_record
    def broken(*args,**kwargs):raise StateError('simulated_local_read_failure')
    store.get_record=broken
    with pytest.raises(RuntimePaused,match='TOOL_LOCAL_PROCESSING_FAILED'):
        await invoke(runtime,tool_profile=['read_record'])
    task=store.get_task('task_fixture');state=json.loads(store.read_artifact(task.response_artifact_path))
    original_call=state['pending_tool']
    assert ledger.get_call(original_call)['state']=='SETTLED' and len(requests)==1
    assert task.status=='PAUSED_PROTOCOL'
    store.get_record=original
    assert (await invoke(runtime,tool_profile=['read_record'])).result.value=='valid'
    assert len(requests)==2 and len(ledger.list_calls())==3
    assert runtime.tool_trace('task_fixture')[0]['call_id']==original_call
    assert runtime.tool_trace('task_fixture')[0]['status']=='error'
    await runtime.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('metadata_only', [False, True])
async def test_bad_finding_quote_pauses_before_acceptance_without_semantic_repair(tmp_path,metadata_only):
    from arc.schemas import Finding,SourceRecord
    class Findings(BaseModel):
        findings:list[Finding]
        contrary_findings:list[Finding]
    responses=[]
    runtime,store,ledger,requests=setup_runtime(tmp_path,responses)
    source=store.register_source(SourceRecord(title='Frozen test material',url='https://example.org/material',
        source_type='paper',access_status='metadata_only' if metadata_only else 'retrieved',
        content_origin='metadata' if metadata_only else 'original'),
        content=None if metadata_only else 'First sentence. Middle sentence. Last sentence.')
    bad_quote='Search snippet presented as paper text.' if metadata_only else 'First sentence. ... Last sentence.'
    finding=Finding(claim='A claimed observation',conditions=[],source_id=source.source_id,
        locator=None,locator_status='locator_unverified',relation='motivates',origin='original',
        excerpt=bad_quote,support_explanation='This is deliberately invalid source attribution.')
    response=answer();response['result']={'findings':[finding.model_dump(mode='json')],'contrary_findings':[]}
    responses.append(sse(json.dumps(response)))
    payload={'source_ids':[source.source_id]}
    for attempt in range(2):
        with pytest.raises(RuntimePaused,match='excerpt_not_in_returned_source'):
            await runtime.invoke('investigator','INVOKE',payload,Findings,SUBJECT,'task_fixture')
    task=store.get_task('task_fixture')
    assert task.status=='PAUSED_PROTOCOL' and task.accepted_result is None
    state=json.loads(store.read_artifact(task.response_artifact_path))
    assert state['repair_count']==0 and bad_quote in state['response']['message']['content']
    assert len(requests)==1 and len(ledger.list_calls())==1 and store.list_evidence()==[]
    await runtime.close()


@pytest.mark.asyncio
async def test_complete_prefix_schema_errors_reach_single_repair_without_accepting_prefix(tmp_path):
    bad = answer()
    del bad['result']['value']
    raw = json.dumps(bad) + ' trailing output'
    runtime, store, ledger, requests = setup_runtime(tmp_path, [sse(raw), sse(json.dumps(answer('repaired')))])
    result = await invoke(runtime)
    assert result.result.value == 'repaired' and len(requests) == 2
    saved = json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
    errors = saved['repair_validation_errors']
    assert errors[0]['type'] == 'json_invalid'
    assert any(e.get('feedback_only') and e['loc'] == ['result', 'value'] for e in errors)
    assert 'complete_json_prefix' in requests[1]['messages'][1]['content']
    assert saved['repair_counts'] == {'tool_arguments': 0, 'output_json': 1}
    await runtime.close()


@pytest.mark.asyncio
async def test_final_structural_diagnostics_persist_without_third_request(tmp_path):
    bad = answer()
    del bad['result']['value']
    runtime, store, ledger, requests = setup_runtime(tmp_path, [sse('{bad'), sse(json.dumps(bad))])
    with pytest.raises(RuntimePaused, match='INVALID_OUTPUT_AFTER_REPAIR'):
        await invoke(runtime)
    saved = json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
    assert any(e['loc'] == ['result', 'value'] and e['type'] == 'missing'
               for e in saved['final_validation_errors'])
    assert len(requests) == 2 and store.get_task('task_fixture').accepted_result is None
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('target, issue_claim, expected', [
    ('issue_new','claim1',None),
    ('issue_missing','claim1','evidence_request_issue_id_not_supplied_to_task'),
    ('issue_new','claim2','evidence_request_issue_claim_mismatch'),
    ('issue_new','invented_claim','evidence_request_issue_id_not_supplied_to_task'),
])
async def test_completed_moderator_can_request_evidence_for_its_declared_new_issue(tmp_path,target,issue_claim,expected):
    from arc.schemas import Envelope, ModeratorResult
    from arc.store import StateError
    runtime, store, ledger, requests = setup_runtime(tmp_path, [])
    raw = request_answer(claim_id='claim1', issue_id=target)
    raw['result'] = {'assessment':'NEEDS_EVIDENCE','next_action':'RETRIEVE','stop_reason':None,
        'concise_ruling':'The original study must be read before deciding.',
        'updated_issues':[{'issue_id':'issue_new','claim_id':issue_claim,'claim_version':1,
            'content':'Nearest prior work needs full-text comparison.','status':'needs_retrieval',
            'evidence_ids':[],'resolution_criterion':'Read the original comparison.',
            'change_this_round':'New objection from the current debate.','next_action':'RETRIEVE'}],
        'issue_transitions':[{'issue_id':'issue_new','from_status':None,'to_status':'needs_retrieval',
            'change_this_round':'New objection.','basis_evidence_ids':[],
            'basis_argument':'The original comparison is missing.','resolution_reason':None}],
        'decisive_evidence_ids':[],'proposed_card_revision':None,
        'external_test_requirements':[],'direction_change':None}
    envelope = Envelope[ModeratorResult].model_validate(raw)
    payload = {'claim_ids':['claim1','claim2'], 'issues':[]}
    if expected:
        with pytest.raises(StateError,match=expected):
            runtime._validate_semantics(envelope,payload,{'tool_trace':[]})
    else:
        runtime._validate_semantics(envelope,payload,{'tool_trace':[]})
    assert requests == [] and store.get_issues(SUBJECT['run_id']) == []
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('target, has_card, allowed', [
    ('claim_new',True,True),('claim_unowned',True,False),('claim_new',False,False)])
@pytest.mark.parametrize('conception', [False, True])
async def test_compose_requests_may_target_claims_declared_in_the_same_card(tmp_path,target,has_card,allowed,conception):
    from arc.schemas import Envelope, ComposeResult, ConceptionResult, Claim
    from arc.store import StateError
    from tests.test_selection import research_store, research_draft
    research_store(tmp_path)
    runtime, store, ledger, requests = setup_runtime(tmp_path, [])
    draft = research_draft()
    draft.claims = [Claim(claim_id='claim_new',version=1,text='A proposed testable effect.',
                         conditions=['Controlled setting'],kind='hypothesis',evidence_ids=[])]
    raw = request_answer(claim_id=target)
    raw['result'] = {'card_candidate':draft.model_dump(mode='json') if has_card else None,
                     'composition_reason':'The question merits testing.', 'unresolved_prerequisites':[]}
    if conception:
        raw['result'].pop('unresolved_prerequisites')
        raw['result'].update(continue_or_stop='CONTINUE', distinct_from_retained='A new question.')
    envelope = Envelope[ConceptionResult if conception else ComposeResult].model_validate(raw)
    payload = {'evidence_ids':['ev_synthetic'],'source_ids':['src_synthetic']}
    if allowed:
        runtime._validate_semantics(envelope,payload,{'tool_trace':[]})
    else:
        with pytest.raises(StateError,match='evidence_request_claim_id_not_supplied_to_task'):
            runtime._validate_semantics(envelope,payload,{'tool_trace':[]})
    assert requests == [] and store.list_tasks(SUBJECT['run_id']) == []
    await runtime.close()
