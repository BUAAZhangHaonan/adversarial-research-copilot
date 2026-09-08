"""Explicit stage orchestration using the actual scientific review/revision cycle."""
from __future__ import annotations
import copy
import json
from dataclasses import asdict
from collections import Counter
import pytest

from arc.config import Settings
from arc.schemas import ScientificReview
from arc.workflows import WorkflowEngine
from tests.test_selection import research_store,research_draft,selection_result
from tests.test_workflows import ScriptedRuntime
from tests.helpers.scientific_cases import scientific_case,register_scientific_case


def review_result(target,*,action='retain',previous=None):
    findings=[]
    if action=='revise':
        findings=[{'finding_id':'partition_gap','location':'/minimal_test/measurements/0',
            'quoted_text':target['minimal_test']['measurements'][0],
            'reason':'全部实例都成功时，三个错误率都为零，所以不恒加和为一。',
            'consequence':'所称全实例分解不穷尽。','evidence_ids':[], 'source_ids':[],
            'severity':'repairable','required_change':'加入完全正确类，保持全实例分母。',
            'acceptance_test':'全成功和全失败的最小例子均给完整分解。'}]
    return {'original_question':target['problem_anchor']['question'],'scope_faithful':True,
        'core_insight':'本合成任务的可检查判别。','value_judgment':'substantial' if action=='retain' else 'routine',
        'value_reason':'测试桩结论，只检验流程，不作为真实科研价值标签。',
        'verification_work':[{'question':'分类是否穷尽目标总体？','method':'counterexample',
            'answer':'用全部成功和全部失败情形核对分母与覆盖。','evidence_ids':[],'source_ids':[]}],
        'decisive_findings':findings,
        'prior_findings':[{'finding_id':f['finding_id'],'status':'resolved','reason':'当前测量包含完全正确类。'}
                          for f in (previous or {}).get('decisive_findings',[])],
        'edit_assessments':[],'remaining_uncertainty':['研究实验尚未执行。'],'action':action}


class ScientificStageRuntime(ScriptedRuntime):
    def __init__(self,*args,repair=False,decision='retain',condition_edit=False,**kwargs):
        super().__init__(*args,**kwargs)
        self.repair=repair
        self.decision=decision
        self.condition_edit=condition_edit

    async def invoke(self,**kwargs):
        envelope=await super().invoke(**kwargs)
        task=self.store.get_task(kwargs['task_id'])
        if task and self.rendered:
            rendered=self.rendered[-1][2]
            path=self.store.save_artifact(f"tests/{task.task_id}.prompt.json",json.dumps(asdict(rendered),ensure_ascii=False))
            self.store.put_task(task.model_copy(update={'rendered_prompt_path':path}))
        return envelope

    def reply(self,role,task,payload,task_id):
        if role=='scientific_reviewer':
            prior=payload.get('previous_review')
            action='revise' if self.repair and prior is None else self.decision
            return review_result(payload['review_target'],action=action,previous=prior)
        if role=='discovery' and task=='REVISE':
            corrected=scientific_case('partition_correct')['model_visible']['card']['minimal_test']
            return {'section_updates':[{'field':'minimal_test','value':corrected}],
                'claim_updates':[],'remove_claim_ids':[],
                'addressed_findings':[{'finding_id':'partition_gap','status':'resolved','reason':'补齐成功类。'}],
                'change_summary':['补齐全实例分类。'],'abandon':False}
        result=super().reply(role,task,payload,task_id)
        if role=='developer' and self.condition_edit:
            result['proposed_revision']['problem_anchor']['conditions'].append('模型初稿中的操作细节调整，原问题不变。')
        return result


@pytest.mark.asyncio
async def test_new_develop_is_one_expansion_and_independent_science_without_debate(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    stage=store.create_run('develop',card_id=card.card_id,card_version=1)
    runtime=ScientificStageRuntime(store)
    result=await WorkflowEngine(store,runtime,Settings()).execute(stage.run_id)
    assert result.status=='COMPLETED' and result.assessment=='PROMISING',result.stop_reason
    assert result.stop_reason=='experiment_required' and result.card_version==2
    assert [call['role'] for call in runtime.calls]==['developer','scientific_reviewer']
    assert result.state['research_flow']=='scientific_v2'
    assert 'fresh_verification' not in result.state and 'rounds_completed' not in result.state
    assert result.state['final_scientific_card_version']==2
    assert store.get_card(card.card_id,2).selection_result.action=='retain'


@pytest.mark.asyncio
async def test_develop_method_conditions_are_reviewed_before_anchor_is_authorized(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    stage=store.create_run('develop',card_id=card.card_id,card_version=1)
    runtime=ScientificStageRuntime(store,condition_edit=True)
    result=await WorkflowEngine(store,runtime,Settings()).execute(stage.run_id)
    assert any(call['role']=='scientific_reviewer' for call in runtime.calls)
    assert result.status=='COMPLETED',result.stop_reason
    assert result.assessment=='PROMISING'
    revised=store.get_card(card.card_id,result.card_version)
    assert revised.draft.problem_anchor.question==card.draft.problem_anchor.question
    assert len(revised.draft.problem_anchor.conditions)==len(card.draft.problem_anchor.conditions)+1


@pytest.mark.asyncio
async def test_new_run_corrects_actual_card_then_rechecks_before_promising(tmp_path):
    store,_,_=research_store(tmp_path)
    card,_=register_scientific_case(store,'partition_faulty',creation_key='initial')
    stage=store.create_run('run',card_id=card.card_id,card_version=1)
    runtime=ScientificStageRuntime(store,repair=True)
    result=await WorkflowEngine(store,runtime,Settings()).execute(stage.run_id)
    assert result.status=='COMPLETED' and result.assessment=='PROMISING',result.stop_reason
    assert [(call['role'],call['task']) for call in runtime.calls]==[
        ('scientific_reviewer','INVOKE'),('discovery','REVISE'),('scientific_reviewer','INVOKE')]
    revised=store.get_card(card.card_id,result.card_version)
    assert '完全正确/N' in revised.draft.minimal_test.measurements[0]
    assert '三项' in store.get_card(card.card_id,1).draft.minimal_test.measurements[0]
    assert result.state['final_scientific_review']['prior_findings'][0]['status']=='resolved'


@pytest.mark.asyncio
async def test_scientific_resume_reuses_expansion_review_and_revision(tmp_path):
    store,_,_=research_store(tmp_path)
    card,_=register_scientific_case(store,'partition_faulty',creation_key='initial')
    stage=store.create_run('run',card_id=card.card_id,card_version=1)
    runtime=ScientificStageRuntime(store,repair=True,fail_once='pressure.science.recheck')
    engine=WorkflowEngine(store,runtime,Settings())
    first=await engine.execute(stage.run_id)
    assert first.status=='PAUSED_EXTERNAL' and first.state['research_flow']=='scientific_v2'
    second=await engine.execute(stage.run_id)
    assert second.status=='COMPLETED' and second.assessment=='PROMISING',second.stop_reason
    counts=Counter(call['task_id'].split(stage.run_id+'.',1)[1] for call in runtime.calls)
    assert counts=={'pressure.science.review':1,'pressure.science.revision':1,'pressure.science.recheck':2}
    count=len(runtime.calls)
    await engine.execute(stage.run_id)
    assert len(runtime.calls)==count


@pytest.mark.asyncio
@pytest.mark.parametrize('decision,assessment',[('needs_evidence','NEEDS_EVIDENCE'),('reject','REJECTED')])
async def test_new_run_preserves_unresolved_or_negative_scientific_result(tmp_path,decision,assessment):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    store.record_selection(None,card.card_id,card.version,selection_result())
    stage=store.create_run('run',card_id=card.card_id,card_version=1)
    runtime=ScientificStageRuntime(store,decision=decision)
    result=await WorkflowEngine(store,runtime,Settings()).execute(stage.run_id)
    assert result.status=='COMPLETED' and result.assessment==assessment
    assert result.card_version==2
    assert store.get_card(card.card_id,1).selection_result.selection=='MAIN_REPORT'
    assert store.get_card(card.card_id,2).selection_result.action==decision
    assert result.state['next_action']=='STOP'


@pytest.mark.asyncio
@pytest.mark.parametrize('state',[{'research_flow':'legacy_debate_v1'},{'rounds_completed':0}])
async def test_explicit_legacy_or_old_checkpoint_resumes_only_original_debate(tmp_path,state):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    stage=store.create_run('run',card_id=card.card_id,card_version=1,state=state)
    runtime=ScientificStageRuntime(store)
    result=await WorkflowEngine(store,runtime,Settings()).execute(stage.run_id)
    assert result.status=='COMPLETED'
    assert result.state['research_flow']=='legacy_debate_v1'
    assert [call['role'] for call in runtime.calls]==['proposer','skeptic','moderator']


@pytest.mark.asyncio
async def test_old_role_config_alone_does_not_silently_select_legacy_flow(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    stage=store.create_run('run',card_id=card.card_id,card_version=1,
        config={'roles':{'moderator':'deepseek-v4-pro'}})
    runtime=ScientificStageRuntime(store)
    result=await WorkflowEngine(store,runtime,Settings()).execute(stage.run_id)
    assert result.state['research_flow']=='scientific_v2'
    assert [call['role'] for call in runtime.calls]==['scientific_reviewer']
