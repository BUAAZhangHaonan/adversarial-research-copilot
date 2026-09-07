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

def sse(text=None, finish='stop', tools=None, reasoning='private reasoning'):
    chunks=[{'id':'req_fixture','object':'chat.completion.chunk','created':1,'model':'deepseek-v4-flash',
             'choices':[{'index':0,'delta':{'role':'assistant','reasoning_content':reasoning},'finish_reason':None}]}]
    delta={'content':text} if tools is None else {'tool_calls':tools}
    chunks.append({'id':'req_fixture','object':'chat.completion.chunk','created':1,'model':'deepseek-v4-flash',
                   'choices':[{'index':0,'delta':delta,'finish_reason':None}]})
    if finish is not None:
        chunks.append({'id':'req_fixture','object':'chat.completion.chunk','created':1,'model':'deepseek-v4-flash',
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
async def test_native_tool_reasoning_association_and_trace(tmp_path):
    calls=[]
    async def read(args,meta):calls.append((args,meta));return {'source_ids':[],'answer':'fixture-data'}
    tool=BoundTool('read_record',{'type':'object','properties':{'record_id':{'type':'string'}},'required':['record_id']},read,Decimal(0),'LOCAL')
    tool_parts=[{'index':0,'id':'provider_tool_1','type':'function','function':{'name':'read_record','arguments':'{"record_id":"record_1"}'}}]
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(finish='tool_calls',tools=tool_parts),sse(json.dumps(answer()))],tools={'read_record':tool})
    await invoke(runtime,tool_profile=['read_record'])
    assert len(calls)==1 and len(requests)==2
    assistant=requests[1]['messages'][-2];reply=requests[1]['messages'][-1]
    assert assistant['reasoning_content']=='private reasoning'
    assert assistant['tool_calls'][0]['id']==reply['tool_call_id']=='provider_tool_1'
    assert 'tool_choice' not in requests[0] and 'response_format' not in requests[0]
    trace=runtime.tool_trace('task_fixture')[0]
    assert trace['status']=='completed' and trace['name']=='read_record'
    assert len(ledger.list_calls())==3
    await runtime.close()

@pytest.mark.asyncio
async def test_semantic_hallucination_not_repaired_into_success(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(answer(evidence_ids=['made_up'])))])
    with pytest.raises(RuntimePaused,match='unknown_evidence_id'):await invoke(runtime)
    assert len(requests)==1 and store.get_task('task_fixture').accepted_result is None
    await runtime.close()

@pytest.mark.asyncio
async def test_repair_cannot_invent_reference(tmp_path):
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse('{}'),sse(json.dumps(answer(evidence_ids=['invented'])))])
    with pytest.raises(RuntimePaused,match='unknown_evidence_id'):await invoke(runtime)
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
    assert excerpt['content'].endswith('DECISIVE_FINAL_SENTENCE') and not excerpt['more_content']


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
