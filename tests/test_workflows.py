"""Three-stage workflow contract tests over SQLite and frozen synthetic evidence."""
from __future__ import annotations

from collections import Counter
import copy
from pathlib import Path

import pytest

from arc.config import Settings
from arc.prompting import PromptLoader
from arc.schemas import Envelope, TaskRecord
from arc.workflows import WorkflowEngine, WorkflowPause, RESEARCH_TOOLS
from tests.test_selection import research_store, research_draft, novelty_result, selection_result

ASSETS=Path(__file__).resolve().parents[1]/'prompts'


class ScriptedRuntime:
    """Mock model replies; exercise actual rendering and store checkpoints."""
    def __init__(self,store,*,empty=False,fail_once=None,fresh_trace=True,repeat=False,request_evidence=False,scope_change=False):
        self.store=store
        self.tools={name:object() for name in RESEARCH_TOOLS}
        self.loader=PromptLoader(ASSETS)
        self.calls=[]
        self.rendered=[]
        self.empty=empty
        self.fail_once=fail_once
        self.failed=False
        self.fresh_trace=fresh_trace
        self.repeat=repeat
        self.request_evidence=request_evidence
        self.scope_change=scope_change

    def tool_trace(self,task_id):
        if not self.fresh_trace:
            return []
        body=self.store.get_record('src_synthetic')['content']
        return [{'name':'read_paper','status':'completed','source_ids':['src_synthetic'],
                 'trace_id':'synthetic-tool-trace','result':{'is_error':False,
                 'source_ids':['src_synthetic'],'sources':[{'source_id':'src_synthetic',
                 'content':body,'content_chars':len(body),'content_total_chars':len(body),
                 'content_complete':True}]}}]

    async def invoke(self,*,role,task,payload,result_schema,subject,task_id,tool_profile,on_admitted=None):
        self.calls.append({'role':role,'task':task,'task_id':task_id,'payload':copy.deepcopy(payload),'tools':list(tool_profile)})
        if self.fail_once and self.fail_once in task_id and not self.failed:
            self.failed=True
            raise WorkflowPause('PAUSED_EXTERNAL','synthetic_service_failure')
        if on_admitted:
            on_admitted()
        rendered=self.loader.render(f'{role}.{task}',{'task_id':task_id,'subject':subject.model_dump(mode='json'),'payload':payload},schema=Envelope[result_schema].model_json_schema(),tool_profile=tool_profile)
        self.rendered.append((role,task_id,rendered))
        if self.request_evidence and role=='selector' and '.after_evidence' not in task_id:
            return Envelope[result_schema](schema_version='arc.v1',task_id=task_id,subject=subject,result_status='needs_evidence',result=None,evidence_requests=[{'request_local_id':'request-coverage','claim_id':'claim_observation','issue_id':None,'draw_id':None,'question':'Does Section 2 establish causation or merely ask the question?','target_source_ids':['src_synthetic'],'queries':[],'purpose':'Resolve nearest-work coverage','decision_if_supported':'Keep the new intervention distinct','decision_if_contradicted':'Record that the contribution is covered'}],capability_requests=[],note='The original section must be checked before selecting.')
        result=result_schema.model_validate(self.reply(role,task,payload,task_id))
        envelope=Envelope[result_schema](schema_version='arc.v1',task_id=task_id,subject=subject,result_status='complete',result=result,evidence_requests=[],capability_requests=[],note=None)
        response_path=self.store.save_artifact(f'tests/{task_id}.json',envelope.model_dump_json())
        self.store.put_task(TaskRecord(task_id=task_id,run_id=subject.run_id,input_hash='synthetic-input',prompt_hash=rendered.prompt_hash,model_config_hash='synthetic-model',status='ACCEPTED',response_artifact_path=response_path,accepted_result=envelope.model_dump(mode='json'),evidence_ids=['ev_synthetic']))
        return envelope

    def reply(self,role,task,payload,task_id):
        if role=='discovery' and task=='FRAME':
            return {'mandate':{'topic':payload['topic'],'research_object':'controlled recall','scope_in':['equal token budget'],'scope_out':['pretraining'],'known_constraints':['3090 24GB'],'unknown_constraints':[]},'initial_search_questions':['Which observed variables covary?']}
        if role=='investigator':
            findings=[]
            if self.scope_change and 'scope_original_audit' in task_id:
                excerpt='The authors ask whether distance or interference caused the result; they do not isolate the variables.'
                original=self.store.read_artifact(self.store.get_source('src_synthetic').content_path)
                start=original.index(excerpt)
                findings=[{'claim':'The prior study did not isolate the variables.','conditions':['synthetic controlled recall task'],'source_id':'src_synthetic','locator':f'chars:{start}:{start+len(excerpt)}','locator_status':'verified','relation':'limits','origin':'original','excerpt':excerpt,'support_explanation':'This original passage confirms the limitation that triggered the frozen suggestion.'}]
            return {'questions_addressed':['Current evidence question'],'actual_searches':[],'findings':findings,'contrary_findings':[],'source_access_limits':[],'implications_for_current_card':['The original observation supports investigation, not the proposed causal result.'],'unresolved_questions':[],'recommended_next_action':'STOP'}
        if role=='discovery' and task=='NEXT_DRAW':
            number=int(task_id.split('.draw')[1].split('.')[0])
            keep_going=self.empty or self.repeat or number==1
            return {'continue_or_stop':'CONTINUE' if keep_going else 'STOP','proposed_family':'Distance versus interference' if keep_going else None,'anchor_evidence_ids':['ev_synthetic'] if keep_going else [],'distinct_from_retained':'A causal intervention, not another task variant.' if keep_going else None,'relevant_archive_relations':[],'missing_information':[],'why_this_draw_is_worthwhile':'Either answer changes the next intervention.' if keep_going else None}
        if role=='discovery' and task=='COMPOSE':
            return {'card_candidate':None if self.empty else research_draft().model_dump(mode='json'),'composition_reason':'No discriminating study supported.' if self.empty else 'Supported controlled contrast.','unresolved_prerequisites':[]}
        if role=='librarian':
            return {'comparisons':[{'archive_card_id':record['card_id'],'archive_card_version':record['version'],'relation':'same_contribution' if self.repeat else 'related_but_distinct','rationale':'Same causal intervention.' if self.repeat else 'The question is shared but the knowledge claim differs.','reopening_condition_met':False} for record in payload['records_to_compare']],
                    'records_opened':[],'retrieval_scope':'Supplied bounded records','unsearched_limits':[],'needs_additional_lookup':False}
        if role=='novelty_examiner':
            return novelty_result().model_dump(mode='json')
        if role=='selector':
            return selection_result().model_dump(mode='json')
        if role=='developer':
            if task=='IMPORT':
                revised=research_draft().model_dump(mode='json')
                revised['problem_anchor']=payload['problem_anchor']
                return {'proposed_revision':revised,'direction_change':None,'unchanged_problem_anchor':payload['problem_anchor'],'change_summary':['Organized user material.'],'affected_claims':[],'evidence_review':[],'minimal_test':revised['minimal_test'],'resources':revised['resources'],'remaining_issues':[],'next_action':'REASON'}
            if self.scope_change:
                anchor=copy.deepcopy(payload['original_card']['draft']['problem_anchor'])
                anchor['question']='Does training distribution explain the mechanism instead?'
                return {'proposed_revision':None,'direction_change':{'proposed_problem_anchor':anchor,'trigger_evidence_ids':['ev_synthetic'],'original_sources_revisited':['src_synthetic'],'missed_evidence_analysis':'The original condition was not considered in the earlier question.'},'unchanged_problem_anchor':payload['original_card']['draft']['problem_anchor'],'change_summary':[],'affected_claims':[],'evidence_review':[],'minimal_test':None,'resources':None,'remaining_issues':[],'next_action':'PROPOSE_SCOPE_CHANGE'}
            revised=copy.deepcopy(payload['original_card']['draft'])
            revised['method']['simplest_path']='Matched two-factor intervention with a positive control.'
            return {'proposed_revision':revised,'direction_change':None,'unchanged_problem_anchor':payload['original_card']['draft']['problem_anchor'],'change_summary':['Clarified the method; question unchanged.'],'affected_claims':[],'evidence_review':[],'minimal_test':revised['minimal_test'],'resources':revised['resources'],'remaining_issues':[],'next_action':'REASON'}
        if role=='proposer':
            return {'claims_defended':['The observation motivates the controlled test.'],'claims_narrowed':[],'claims_withdrawn':[],'proposed_method_changes':[],'issue_responses':[],'new_argument_or_evidence':['A positive control makes the null outcome interpretable.'],'suggested_next_action':'HANDOFF_EXPERIMENT'}
        if role=='skeptic':
            return {'criticisms':[],'resolved_objections':[],'surviving_decisive_issues':[],'required_evidence_or_test':['Run the proposed controlled test.'],'suggested_next_action':'HANDOFF_EXPERIMENT'}
        if role=='moderator':
            return {'assessment':'PROMISING','next_action':'HANDOFF_EXPERIMENT','stop_reason':'Text cannot establish the new empirical result.','concise_ruling':'The test is worth the human investigation.','issue_transitions':[],'updated_issues':[],'decisive_evidence_ids':['ev_synthetic'],'proposed_card_revision':None,'external_test_requirements':['Run the controlled experiment with validity checks.'],'direction_change':None}
        raise AssertionError((role,task))


def campaign_run(store,max_draws=5):
    campaign=store.create_campaign('Controlled recall mechanisms',max_draws=max_draws)
    run=store.create_run('discover',campaign_id=campaign.campaign_id,state={'evidence_ids':['ev_synthetic'],'source_ids':['src_synthetic']})
    return campaign,run


@pytest.mark.asyncio
async def test_five_failed_draws_share_investigation_and_never_fake_a_card(tmp_path):
    store,_,_=research_store(tmp_path)
    campaign,run=campaign_run(store)
    runtime=ScriptedRuntime(store,empty=True)
    result=await WorkflowEngine(store,runtime,Settings()).execute(run.run_id)
    assert result.status=='COMPLETED'
    assert result.stop_reason=='draw_quota_exhausted'
    assert store.get_campaign(campaign.campaign_id).draws_started==5
    assert len(store.list_cards(run_id=run.run_id))==0
    assert Counter(c['role'] for c in runtime.calls)['investigator']==1
    assert len([c for c in runtime.calls if c['task']=='COMPOSE'])==5


@pytest.mark.asyncio
async def test_one_good_card_then_no_distinct_direction_stops_before_five(tmp_path):
    store,_,_=research_store(tmp_path)
    campaign,run=campaign_run(store)
    runtime=ScriptedRuntime(store)
    result=await WorkflowEngine(store,runtime,Settings()).execute(run.run_id)
    assert result.status=='COMPLETED' and result.stop_reason=='no_distinct_direction'
    cards=store.list_cards(run_id=run.run_id)
    assert len(cards)==1 and cards[0].selection=='MAIN_REPORT'
    assert store.get_campaign(campaign.campaign_id).draws_started<5
    assert len([c for c in runtime.calls if c['task']=='COMPOSE'])==1
    assert not any(c['role'] in {'developer','proposer','skeptic','moderator'} for c in runtime.calls)
    second=next(c for c in runtime.calls if '.draw2.next' in c['task_id'])
    assert second['payload']['previous_draws']


@pytest.mark.asyncio
async def test_failure_before_draw_admission_does_not_spend_draw_or_repeat_shared_work(tmp_path):
    store,_,_=research_store(tmp_path)
    campaign,run=campaign_run(store,max_draws=1)
    runtime=ScriptedRuntime(store,empty=True,fail_once='draw1.next')
    engine=WorkflowEngine(store,runtime,Settings())
    first=await engine.execute(run.run_id)
    assert first.status=='PAUSED_EXTERNAL'
    assert store.get_campaign(campaign.campaign_id).draws_started==0
    second=await engine.execute(run.run_id)
    assert second.status=='COMPLETED'
    assert store.get_campaign(campaign.campaign_id).draws_started==1
    assert Counter(c['role'] for c in runtime.calls)['investigator']==1
    assert len([c for c in runtime.calls if c['task']=='FRAME'])==1


@pytest.mark.asyncio
async def test_three_stages_keep_same_card_and_full_anchor_without_auto_transition(tmp_path):
    store,_,_=research_store(tmp_path)
    _,run=campaign_run(store,max_draws=1)
    runtime=ScriptedRuntime(store)
    engine=WorkflowEngine(store,runtime,Settings())
    await engine.execute(run.run_id)
    card=store.list_cards(run_id=run.run_id)[0]
    original=card.draft.model_dump(mode='json')
    development=store.create_run('develop',card_id=card.card_id,card_version=1)
    developed=await engine.execute(development.run_id)
    assert developed.status=='COMPLETED' and developed.card_id==card.card_id and developed.card_version==2
    assert store.get_card(card.card_id,1).draft.model_dump(mode='json')==original
    assert store.get_card(card.card_id,2).draft.problem_anchor==card.draft.problem_anchor
    assert not any(c['task_id'].startswith('run.') for c in runtime.calls)
    review=store.create_run('run',card_id=card.card_id,card_version=2)
    reviewed=await engine.execute(review.run_id)
    assert reviewed.status=='COMPLETED' and reviewed.card_version==2
    assert reviewed.assessment=='PROMISING' and reviewed.stop_reason=='experiment_required'
    for call in runtime.calls:
        if call['role'] in {'developer','proposer','skeptic','moderator'}:
            inherited=call['payload']['card']
            assert inherited['card_id']==card.card_id
            assert inherited['draft']['problem_anchor']==original['problem_anchor']
            assert call['payload']['evidence'][0]['evidence_id']=='ev_synthetic'
            assert call['payload']['sources'][0]['source_id']=='src_synthetic'


@pytest.mark.asyncio
async def test_develop_requires_real_trace_not_claimed_fresh_verification(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    run=store.create_run('develop',card_id=card.card_id,card_version=1)
    runtime=ScriptedRuntime(store,fresh_trace=False)
    result=await WorkflowEngine(store,runtime,Settings()).execute(run.run_id)
    assert result.status=='PAUSED_EXTERNAL'
    assert result.stop_reason=='fresh_verification_not_executed'
    assert not any(c['role']=='developer' for c in runtime.calls)
    assert store.get_card(card.card_id).version==1


@pytest.mark.asyncio
async def test_resume_reuses_proposer_skeptic_and_long_context_tail(tmp_path):
    store,_,_=research_store(tmp_path)
    draft=research_draft()
    marker='DECISIVE_TAIL_CONDITION_DO_NOT_DROP'
    draft.problem_anchor.conditions.append('边界说明 '*4000+marker)
    card=store.save_card(draft)
    run=store.create_run('run',card_id=card.card_id,card_version=1)
    runtime=ScriptedRuntime(store,fail_once='round1.moderator')
    engine=WorkflowEngine(store,runtime,Settings())
    first=await engine.execute(run.run_id)
    assert first.status=='PAUSED_EXTERNAL'
    second=await engine.execute(run.run_id)
    assert second.status=='COMPLETED'
    counts=Counter(c['role'] for c in runtime.calls)
    assert counts['proposer']==1 and counts['skeptic']==1 and counts['moderator']==2
    for role,_,rendered in runtime.rendered:
        if role in {'proposer','skeptic','moderator'}:
            assert marker in rendered.messages[1]['content']


@pytest.mark.asyncio
async def test_resuming_at_round_limit_makes_no_new_call(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    run=store.create_run('run',card_id=card.card_id,card_version=1,state={'rounds_completed':1})
    runtime=ScriptedRuntime(store)
    result=await WorkflowEngine(store,runtime,Settings(max_rounds=1)).execute(run.run_id)
    assert result.status=='COMPLETED' and result.stop_reason=='max_rounds_reached'
    assert runtime.calls==[]


@pytest.mark.asyncio
async def test_same_contribution_cannot_fill_multiple_draws_by_rewording(tmp_path):
    store,_,_=research_store(tmp_path)
    _,run=campaign_run(store,max_draws=2)
    runtime=ScriptedRuntime(store,repeat=True)
    result=await WorkflowEngine(store,runtime,Settings()).execute(run.run_id)
    cards=store.list_cards(run_id=run.run_id)
    assert len([c for c in cards if c.selection=='MAIN_REPORT'])<=1
    assert result.status in {'COMPLETED','PAUSED_PROTOCOL','PAUSED_EXTERNAL'}


@pytest.mark.asyncio
async def test_needs_evidence_executes_targeted_check_then_revisits_exact_selection(tmp_path):
    store,_,_=research_store(tmp_path)
    _,run=campaign_run(store,max_draws=1)
    runtime=ScriptedRuntime(store,request_evidence=True)
    result=await WorkflowEngine(store,runtime,Settings()).execute(run.run_id)
    assert result.status=='COMPLETED'
    requests=[call for call in runtime.calls if 'selection.requested_evidence' in call['task_id']]
    assert len(requests)==1
    request=requests[0]['payload']['evidence_requests'][0]
    assert request['target_source_ids']==['src_synthetic']
    assert 'Section 2' in request['question']
    reconsidered=next(call for call in runtime.calls if call['role']=='selector' and '.after_evidence' in call['task_id'])
    assert reconsidered['payload']['completed_evidence_requests'][0]['request_local_id']=='request-coverage'
    assert reconsidered['payload']['card']['card_id']==store.list_cards(run_id=run.run_id)[0].card_id


@pytest.mark.asyncio
async def test_scope_change_audits_original_freezes_once_and_does_not_develop_branch(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    original=card.draft.model_dump(mode='json')
    run=store.create_run('develop',card_id=card.card_id,card_version=1)
    runtime=ScriptedRuntime(store,scope_change=True)
    engine=WorkflowEngine(store,runtime,Settings())
    result=await engine.execute(run.run_id)
    assert result.status=='PAUSED_SCOPE_CHANGE' and result.assessment=='SCOPE_CHANGE_PROPOSED'
    changes=store.list_direction_changes(run.run_id)
    assert len(changes)==1 and changes[0].status=='FROZEN'
    assert changes[0].parent_card_id==card.card_id
    assert store.get_card(card.card_id).version==1
    assert store.get_card(card.card_id,1).draft.model_dump(mode='json')==original
    assert len([call for call in runtime.calls if 'scope_original_audit' in call['task_id']])==1
    assert not any(call['role'] in {'proposer','skeptic','moderator'} for call in runtime.calls)
    calls=len(runtime.calls)
    await engine.execute(run.run_id)
    assert len(runtime.calls)==calls and len(store.list_direction_changes(run.run_id))==1


@pytest.mark.asyncio
async def test_context_contains_only_relevant_evidence_not_entire_archive(tmp_path):
    store,_,_=research_store(tmp_path)
    from arc.schemas import SourceRecord
    store.register_source(SourceRecord(source_id='src_unrelated',title='PRIVATE_UNRELATED_RECORD',url=None,source_type='user_material',access_status='retrieved',content_origin='original'),content='Unrelated material.')
    card=store.save_card(research_draft())
    run=store.create_run('run',card_id=card.card_id,card_version=1)
    runtime=ScriptedRuntime(store)
    await WorkflowEngine(store,runtime,Settings()).execute(run.run_id)
    for call in runtime.calls:
        assert [source['source_id'] for source in call['payload']['sources']]==['src_synthetic']
    assert all('PRIVATE_UNRELATED_RECORD' not in rendered.messages[1]['content'] for _,_,rendered in runtime.rendered)


@pytest.mark.asyncio
async def test_explicit_user_question_import_does_not_invoke_discovery(tmp_path):
    store,_,_=research_store(tmp_path)
    question='Which intervention distinguishes the existing two explanations?'
    run=store.create_run('run',state={'imported_input':question,'evidence_ids':['ev_synthetic'],'source_ids':['src_synthetic']})
    runtime=ScriptedRuntime(store)
    result=await WorkflowEngine(store,runtime,Settings()).execute(run.run_id)
    assert result.status=='COMPLETED' and result.card_version==1
    assert store.get_card(result.card_id,1).draft.problem_anchor.question==question
    assert runtime.calls[0]['role']=='developer' and runtime.calls[0]['task']=='IMPORT'
    assert not any(call['role']=='discovery' for call in runtime.calls)


@pytest.mark.asyncio
async def test_scope_change_cannot_claim_original_revisit_without_read_trace(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    run=store.create_run('develop',card_id=card.card_id,card_version=1)
    class NoOriginalRead(ScriptedRuntime):
        def tool_trace(self,task_id):
            return [] if 'scope_original_audit' in task_id else super().tool_trace(task_id)
    runtime=NoOriginalRead(store,scope_change=True)
    result=await WorkflowEngine(store,runtime,Settings()).execute(run.run_id)
    assert result.status=='PAUSED_EXTERNAL'
    assert result.stop_reason=='scope_original_sources_not_revisited'
    assert store.list_direction_changes(run.run_id)==[]


@pytest.mark.asyncio
async def test_issue_commit_and_round_checkpoint_survive_postcommit_crash(tmp_path,monkeypatch):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    run=store.create_run('run',card_id=card.card_id,card_version=1)
    runtime=ScriptedRuntime(store)
    engine=WorkflowEngine(store,runtime,Settings())
    apply=store.apply_issues
    def commit_then_crash(*args,**kwargs):
        apply(*args,**kwargs)
        raise RuntimeError('SIMULATED_POSTCOMMIT_CRASH')
    monkeypatch.setattr(store,'apply_issues',commit_then_crash)
    with pytest.raises(RuntimeError,match='SIMULATED_POSTCOMMIT_CRASH'):
        await engine.execute(run.run_id)
    persisted=store.get_run(run.run_id)
    assert persisted.state['rounds_completed']==1
    assert persisted.state['final_ruling']['next_action']=='HANDOFF_EXPERIMENT'
    counts=Counter(call['role'] for call in runtime.calls)
    monkeypatch.setattr(store,'apply_issues',apply)
    resumed=await engine.execute(run.run_id)
    assert resumed.status=='COMPLETED' and resumed.assessment=='PROMISING'
    assert Counter(call['role'] for call in runtime.calls)==counts


@pytest.mark.asyncio
async def test_selection_commit_also_commits_finished_draw(tmp_path,monkeypatch):
    store,_,_=research_store(tmp_path)
    campaign,run=campaign_run(store,max_draws=1)
    runtime=ScriptedRuntime(store)
    engine=WorkflowEngine(store,runtime,Settings())
    record=store.record_selection
    def commit_then_crash(*args,**kwargs):
        record(*args,**kwargs)
        raise RuntimeError('SIMULATED_SELECTION_COMMIT_CRASH')
    monkeypatch.setattr(store,'record_selection',commit_then_crash)
    with pytest.raises(RuntimeError,match='SIMULATED_SELECTION_COMMIT_CRASH'):
        await engine.execute(run.run_id)
    saved=store.get_run(run.run_id)
    assert store.list_cards(run_id=run.run_id)[0].selection=='MAIN_REPORT'
    assert saved.state['draws'][f'{campaign.campaign_id}.draw1']['finished'] is True
    monkeypatch.setattr(store,'record_selection',record)
    counts=Counter(call['role'] for call in runtime.calls)
    resumed=await engine.execute(run.run_id)
    assert resumed.status=='COMPLETED'
    assert Counter(call['role'] for call in runtime.calls)==counts


@pytest.mark.asyncio
async def test_changed_claim_reselects_instead_of_inheriting_old_version_evidence_in_develop(tmp_path):
    from arc.schemas import Claim
    from arc.store import StateError
    store,_,_=research_store(tmp_path)
    draft=research_draft()
    draft.claims=[Claim(claim_id='claim_observation',version=1,text='Distance and distractor count covary.',conditions=['synthetic controlled recall task'],kind='empirical',evidence_ids=['ev_synthetic'])]
    card=store.save_card(draft)
    run=store.create_run('develop',card_id=card.card_id,card_version=1)
    class ChangedClaim(ScriptedRuntime):
        def reply(self,role,task,payload,task_id):
            result=super().reply(role,task,payload,task_id)
            if role=='developer':
                claim=result['proposed_revision']['claims'][0]
                claim.update(version=2,text='Distance alone causes the entire decrease.')
                result['affected_claims']=['claim_observation']
                result['evidence_review']=[{'claim_id':'claim_observation','claim_version':2,'evidence_ids':['ev_synthetic'],'still_applicable':True,'explanation':'A claimed reuse cannot upgrade the original claim version.'}]
            return result
    runtime=ChangedClaim(store)
    result=await WorkflowEngine(store,runtime,Settings()).execute(run.run_id)
    assert result.status=='COMPLETED'
    assert store.get_card(card.card_id).version==2
    assert store.get_card(card.card_id).draft.claims[0].evidence_ids==[]
    assert store.get_card(card.card_id,1).draft.claims[0].evidence_ids==['ev_synthetic']
    recheck=next(call for call in runtime.calls if call['task_id'].endswith('development.evidence_recheck'))
    assert recheck['payload']['card']['draft']['claims'][0]['version']==2
    assert recheck['payload']['target_source_ids']==['src_synthetic']
    assert any(call['role']=='moderator' for call in runtime.calls)


@pytest.mark.asyncio
async def test_moderator_receives_previous_issue_and_cannot_silently_drop_it(tmp_path):
    from arc.schemas import Claim,Issue,IssueTransition
    from arc.store import StateError
    store,_,_=research_store(tmp_path)
    draft=research_draft()
    draft.claims=[Claim(claim_id='claim_observation',version=1,text='Distance and distractor count covary.',conditions=['synthetic controlled recall task'],kind='empirical',evidence_ids=['ev_synthetic'])]
    card=store.save_card(draft)
    run=store.create_run('run',card_id=card.card_id,card_version=1)
    issue=Issue(issue_id='issue_old',claim_id='claim_observation',claim_version=1,content='Two factors still covary.',status='needs_experiment',evidence_ids=['ev_synthetic'],resolution_criterion='Separate factors with a validated intervention.',change_this_round='Original unresolved issue.',next_action='HANDOFF_EXPERIMENT')
    transition=IssueTransition(issue_id='issue_old',from_status=None,to_status='needs_experiment',change_this_round='Registered from original evidence.',basis_evidence_ids=['ev_synthetic'],basis_argument=None,resolution_reason=None)
    store.apply_issues(run.run_id,[issue],[transition])
    runtime=ScriptedRuntime(store)
    result=await WorkflowEngine(store,runtime,Settings()).execute(run.run_id)
    assert result.status=='PAUSED_PROTOCOL' and result.stop_reason=='previous_issue_silently_dropped'
    moderator=next(call for call in runtime.calls if call['role']=='moderator')
    assert moderator['payload']['issues'][0]['issue_id']=='issue_old'
    assert moderator['payload']['issues'][0]['resolution_criterion']==issue.resolution_criterion
    assert store.get_issues(run.run_id)==[issue]
    assert store.get_run(run.run_id).status!='COMPLETED'

@pytest.mark.asyncio
async def test_cached_invalid_finding_stays_protocol_paused_without_new_draw_or_paid_replay(tmp_path):
    store,_,_=research_store(tmp_path)
    campaign=store.create_campaign('Research topic')
    run=store.create_run('discover',campaign_id=campaign.campaign_id)
    class BadFindingRuntime(ScriptedRuntime):
        def reply(self,role,task,payload,task_id):
            result=super().reply(role,task,payload,task_id)
            if role=='investigator':
                result['findings']=[{'claim':'Unverified assertion','conditions':[],
                    'source_id':'src_synthetic','locator':None,'locator_status':'locator_unverified',
                    'relation':'motivates','origin':'original','excerpt':'A fabricated quotation.',
                    'support_explanation':'This deliberately fails original passage validation.'}]
            return result
    runtime=BadFindingRuntime(store)
    engine=WorkflowEngine(store,runtime,Settings())
    evidence_before=store.list_evidence()
    first=await engine.execute(run.run_id)
    calls_before=len(runtime.calls)
    second=await engine.execute(run.run_id)
    assert first.status==second.status=='PAUSED_PROTOCOL'
    assert first.stop_reason==second.stop_reason=='excerpt_not_in_returned_source'
    assert len(runtime.calls)==calls_before and store.list_evidence()==evidence_before
    assert store.get_campaign(campaign.campaign_id).draws_started==0
    assert store.list_cards(run_id=run.run_id)==[]

@pytest.mark.asyncio
async def test_discovery_frame_receives_seed_material_provenance_before_new_searches(tmp_path):
    store,_,_=research_store(tmp_path)
    campaign=store.create_campaign('Research topic')
    run=store.create_run('discover',campaign_id=campaign.campaign_id,
        state={'source_ids':['src_synthetic'],'evidence_ids':['ev_synthetic']})
    runtime=ScriptedRuntime(store)
    await WorkflowEngine(store,runtime,Settings()).execute(run.run_id)
    frame=runtime.calls[0]
    assert frame['task']=='FRAME'
    assert [s['source_id'] for s in frame['payload']['sources']]==['src_synthetic']
    assert [e['evidence_id'] for e in frame['payload']['evidence']]==['ev_synthetic']
    stored=store.get_run(run.run_id).state['task_inputs']['frame']['payload']
    assert stored['sources']==frame['payload']['sources']
