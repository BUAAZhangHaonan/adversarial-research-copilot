from __future__ import annotations

import copy
import json
from pathlib import Path
from urllib.parse import unquote
import re

import pytest

from arc.prompting import PromptLoader
from arc.reports import render_run

ASSETS=Path(__file__).resolve().parents[1]/'prompts'


def card(selection='MAIN_REPORT',card_id='card-1'):
    return {'card_id':card_id,'version':2,'selection':selection,'assessment':'PROMISING' if selection=='MAIN_REPORT' else 'NEEDS_EVIDENCE' if selection=='LEAD_ONLY' else 'REJECTED',
            'selection_result':{'why_worth_investigating':'已登记判断的原句，不能改变。','decisive_risks':['最致命风险：测量无法分离两个因素'],'next_action':'HANDOFF_EXPERIMENT','reopening_condition':'拿到分离测量后重新判断','evidence_ids':['e-1']},
            'draft':{'title':'题目 [原文] | 中文','problem_anchor':{'question':'问题含 {{ 7 * 7 }} 与 `code`','research_object':'模型','conditions':['同预算'],'anti_scope':['不训练大模型']},
                     'contribution':{'knowledge_increment':'区分两个解释','decision_changed':'决定下一项研究'},
                     'motivation':{'observation_or_deficit':'已支持的异常','evidence_ids':['e-1'],'unresolved_assumptions':['假设未验证']},
                     'closest_work_delta':{'source_ids':['s-1'],'established_claim':'已有结果','remaining_claim':'待检验区分'},
                     'hypotheses':{'main_or_competing_explanations':['解释甲','解释乙'],'distinct_predictions':['不同预测'],'favored_only_if_justified':None},
                     'method':{'simplest_path':'只改变一个因素','necessary_components':[],'stitching_assessment':'无多余组合'},
                     'minimal_test':{'intervention':'改变距离','controls':['长度固定'],'measurements':['召回'],'positive_controls':['简单有效性检查'],'outcome_interpretations':['阴性结果也需检查测量有效性'],'confounds_not_yet_ruled_out':['任务分布']},
                     'resources':{'gpu_type':'RTX 3090','gpu_memory_gb_assumption':24,'gpu_count':1,'training_gpu_hours_range':None,'inference_gpu_hours_range':{'lower':1,'upper':4,'unit':'GPU-hours'},'estimate_basis':'公开记录外推','uncertainty':'较大'},
                     'risks':{'decisive_risks':['测量风险'],'missing_prerequisites':['需要原始方法章节'],'reopen_conditions':['拿到方法章节']}}}


class FakeLedger:
    def __init__(self,path): pass
    def summary(self,account_id):
        return {'account_id':account_id,'limit_cny':'20.000000','spent_lower_cny':'1.250000','spent_upper_cny':'1.250000','reserved_cny':'2.000000','remaining_cny':'16.750000','unknown_calls':1,'currency':'CNY'}
    def list_calls(self,account_id):
        return [{'call_id':'call-1','account_id':account_id,'status':'UNKNOWN','cost_status':'unknown','reserved_cny':'2.000000','cost_estimate_lower':'0.000000','cost_estimate_upper':None}]


class FakeStore:
    def claim_evidence_bindings(self, draft): return []
    def __init__(self,tmp_path):
        self.db_path=tmp_path/'state.sqlite'
        self.artifact_root=tmp_path/'artifacts'
        self.cards=[card(),card('LEAD_ONLY','card-2'),card('NOT_RETAINED','card-3')]
        self.run={'run_id':'run-1','mode':'discover','status':'PAUSED_BUDGET','stop_reason':'next_request_not_admitted','budget_account_id':'budget-1','assessment':None,'campaign_id':'campaign-1','config':{'api_key':'must-not-appear'}}
        self.tasks=[{'task_id':'task-1','status':'ACCEPTED','accepted_result':{'scientific_fact':'仅原有判断'},'evidence_ids':['e-1'],'model_id':'deepseek-v4-flash','prompt_hash':'hash'}, {'task_id':'task-2','status':'UNKNOWN','error':'尚未确认远端结果'}]
    def get_run(self,run_id): return self.run
    def list_cards(self,**kwargs): return self.cards
    def get_card(self,card_id,version):
        return next(card for card in self.cards if card['card_id']==card_id and card['version']==version)
    def list_evidence(self,**kwargs):
        return [{'evidence_id':'e-1','source_id':'s-1','claim':'文献中的具体主张','conditions':['特定分布'],'relation':'motivates','origin':'secondary_analysis','locator_status':'locator_unverified','verification_status':'unverified'}]
    def list_sources(self, ids=None):
        sources = [{'source_id':'s-1','title':'作者论文 [甲] | 数据','url':'https://example.org/paper?q=(one)'}, {'source_id':'s-private','title':'不相关秘密','url':'https://example.org/private'}]
        return sources if ids is None else [source for source in sources if source['source_id'] in ids]
    def get_issues(self,run_id):
        return [{'issue_id':'issue-1','status':'needs_experiment','content':'需要实际测试区分解释','resolution_criterion':'有有效性检查','change_this_round':'已固定控制变量'}]
    def list_direction_changes(self,run_id):
        return [{'proposed_problem_anchor':{'question':'特殊转向'},'original_sources_revisited':['s-1'],'missed_evidence_analysis':'先前忽略条件不同','trigger_evidence_ids':['e-1'],'status':'FROZEN'}]
    def list_tasks(self,run_id): return self.tasks
    def list_capability_requests(self,run_id):
        return [{'blocked_question':'缺少原始章节','needed_operation':'read_web','cost_visibility_needs':'可核查上界','acceptance_example':'返回原文与定位'}]


def test_report_preserves_state_judgments_versions_and_costs(tmp_path,monkeypatch):
    monkeypatch.setattr('arc.budget.BudgetLedger',FakeLedger)
    store=FakeStore(tmp_path)
    before=copy.deepcopy(store.__dict__)
    paths=render_run(store,'run-1',tmp_path/'output',PromptLoader(ASSETS))
    assert store.__dict__==before
    report=paths['overview'].read_text(encoding='utf-8')
    detail=paths['card:card-1:2'].read_text(encoding='utf-8')
    assert '1 张进入主报告，1 张为待补证线索' in report
    assert '已登记判断的原句，不能改变。' in report
    assert 'next_request_not_admitted' in report
    assert 'arc resume run-1' in report
    assert '未完成 1 项' in report
    assert '预算' not in detail or '同预算' in detail
    assert '{{ 7 * 7 }}' in detail and '49' not in detail
    assert '版本 2' in detail and 'RTX 3090' in detail
    assert 'https://example.org/paper?q=%28one%29' in detail
    assert 'must-not-appear' not in report
    assert '不相关秘密' not in report
    assert '特殊转向' in report and '已冻结' in report
    assert 'unknown' in paths['cost'].read_text(encoding='utf-8')
    trace=paths['trace'].read_text(encoding='utf-8')
    assert 'secondary_analysis' in trace and 'locator_unverified' in trace
    assert 'accepted/task-1.json' in trace
    assert json.loads((tmp_path/'output/accepted/task-1.json').read_text(encoding='utf-8'))==store.tasks[0]['accepted_result']
    assert paths['capabilities'].is_file()
    assert '{{ report_title }}' not in report
    for target in re.findall(r'\]\(([^)]+)\)',report):
        if not target.startswith('https://'):
            assert (paths['overview'].parent/unquote(target)).exists()


def test_background_evidence_binding_is_visible_without_promoting_claim(tmp_path):
    from arc.schemas import Claim
    from arc.workflows import WorkflowEngine
    from arc.config import Settings
    from tests.test_selection import research_store, research_draft
    store, _, ev = research_store(tmp_path)
    draft = research_draft()
    draft.claims = [Claim(claim_id='new_hypothesis', version=1,
        text='The independently controlled distance intervention changes recall.',
        conditions=['fixed token budget'], kind='hypothesis', evidence_ids=[ev.evidence_id])]
    saved = store.save_card(draft)
    run = store.create_run('run', card_id=saved.card_id, card_version=1)
    original = store.list_evidence(ids=[ev.evidence_id])[0]
    context = WorkflowEngine(store, None, Settings()).context(run.run_id)
    assert context['claim_evidence_bindings'][0]['binding'] == 'background_premise'
    assert context['claim_evidence_bindings'][0]['verification_transferred'] is False
    paths = render_run(store, run.run_id, tmp_path / 'binding-report')
    report = paths[f'card:{saved.card_id}:1'].read_text(encoding='utf-8')
    assert '背景依据' in report and '不转移验证状态' in report
    displayed = report.replace('\\_', '_')
    assert 'new_hypothesis' in displayed and ev.claim_id in displayed and ev.evidence_id in displayed
    assert store.list_evidence(ids=[ev.evidence_id])[0] == original


@pytest.mark.parametrize('reference_location', ['motivation', 'claim', 'issue', 'run'])
def test_cross_run_report_resolves_only_referenced_inherited_evidence(tmp_path, monkeypatch, reference_location):
    from arc.schemas import Claim, Issue, IssueTransition, SourceRecord
    from tests.test_selection import research_store, research_draft

    store, source, template_evidence = research_store(tmp_path)
    origin = store.create_run('discover', run_id='run_origin')
    inherited = store.register_evidence(template_evidence.model_copy(update={
        'evidence_id': 'ev_inherited', 'run_id': origin.run_id}))
    unrelated_source = store.register_source(SourceRecord(
        source_id='src_unrelated', title='Unrelated private material', url='https://example.org/unrelated',
        source_type='user_material', access_status='retrieved', content_origin='original'),
        content='UNRELATED SOURCE. ' + store.read_artifact(source.content_path))
    store.register_evidence(template_evidence.model_copy(update={
        'evidence_id': 'ev_unrelated', 'source_id': unrelated_source.source_id, 'run_id': origin.run_id,
        'locator': None, 'locator_status': 'locator_unverified', 'verification_status': 'unverified'}))
    draft = research_draft()
    draft.motivation.evidence_ids = []
    draft.closest_work_delta.source_ids = []
    draft.claims = [Claim(claim_id='claim_target', version=1, text='A conditional hypothesis.',
                          conditions=[], kind='hypothesis', evidence_ids=[])]
    if reference_location == 'motivation':
        draft.motivation.evidence_ids = [inherited.evidence_id]
    elif reference_location == 'claim':
        draft.claims[0].evidence_ids = [inherited.evidence_id]
    card_record = store.save_card(draft)
    run = store.create_run('develop', run_id='run_current', card_id=card_record.card_id, card_version=1,
        state={'evidence_ids': [inherited.evidence_id]} if reference_location == 'run' else {})
    if reference_location == 'issue':
        store.apply_issues(run.run_id, [Issue(issue_id='issue_current', claim_id='claim_target', claim_version=1,
            content='Existing observation needs a separating test.', status='needs_experiment',
            evidence_ids=[inherited.evidence_id], resolution_criterion='A controlled intervention.',
            change_this_round='Opened with inherited observation.', next_action='HANDOFF_EXPERIMENT',
            claim_kind='hypothesis')], [IssueTransition(issue_id='issue_current', from_status=None,
            to_status='needs_experiment', change_this_round='Opened with inherited observation.',
            basis_evidence_ids=[inherited.evidence_id], basis_argument=None, resolution_reason=None)])
    assert store.list_evidence(run_id=run.run_id) == []
    store.register_evidence(template_evidence.model_copy(update={
        'evidence_id': 'ev_current_unreferenced', 'run_id': run.run_id}))
    before = (store.get_run(run.run_id), store.get_card(card_record.card_id, 1),
              store.list_evidence(), store.list_sources(), store.get_issues(run.run_id))
    get_evidence, get_sources = store.list_evidence, store.list_sources

    def scoped_evidence(ids=None, run_id=None):
        assert ids is not None or run_id is not None, 'Report must not scan all evidence'
        return get_evidence(ids=ids, run_id=run_id)

    def scoped_sources(ids=None):
        assert ids is not None, 'Report must not scan all sources'
        assert unrelated_source.source_id not in ids
        return get_sources(ids=ids)

    with monkeypatch.context() as patch:
        patch.setattr(store, 'list_evidence', scoped_evidence)
        patch.setattr(store, 'list_sources', scoped_sources)
        paths = render_run(store, run.run_id, tmp_path / 'inherited-report')
    trace = paths['trace'].read_text(encoding='utf-8')
    assert inherited.evidence_id in trace and inherited.source_id in trace
    assert '证据登记运行：run_origin' in trace
    assert inherited.locator in trace
    assert all(eid not in trace for eid in ['ev_unrelated', 'ev_synthetic', 'ev_current_unreferenced'])
    overview = paths['overview'].read_text(encoding='utf-8')
    detail = paths[f'card:{card_record.card_id}:1'].read_text(encoding='utf-8')
    for name, contents in [('overview', overview), ('detail', detail)]:
        if name == 'detail' and reference_location == 'run':
            continue  # A run-only source is not attributed to a card that never cited it.
        links = [unquote(value) for value in re.findall(r'\]\(([^)]+)\)', contents)]
        report_dir = paths['overview' if name == 'overview' else f'card:{card_record.card_id}:1'].parent
        assert any((report_dir / link).resolve() == (store.artifact_root / source.content_path).resolve()
                   for link in links)
    assert all('Unrelated private material' not in text and 'https://example.org/unrelated' not in text
               for text in [overview, detail, trace])
    after = (store.get_run(run.run_id), store.get_card(card_record.card_id, 1),
             store.list_evidence(), store.list_sources(), store.get_issues(run.run_id))
    assert after == before
    assert store.list_evidence(ids=[inherited.evidence_id])[0].run_id == origin.run_id


def test_deterministic_report_rebuild_and_empty_discovery(tmp_path,monkeypatch):
    monkeypatch.setattr('arc.budget.BudgetLedger',FakeLedger)
    store=FakeStore(tmp_path)
    store.cards=[]
    first=render_run(store,'run-1',tmp_path/'output',PromptLoader(ASSETS))
    before={key:path.read_bytes() for key,path in first.items()}
    second=render_run(store,'run-1',tmp_path/'output',PromptLoader(ASSETS))
    assert before=={key:path.read_bytes() for key,path in second.items()}
    assert '不能据此断言整个领域没有研究空间' in first['overview'].read_text(encoding='utf-8')


def test_report_rejects_path_derived_from_title_or_untrusted_id(tmp_path,monkeypatch):
    monkeypatch.setattr('arc.budget.BudgetLedger',FakeLedger)
    store=FakeStore(tmp_path)
    store.cards=[card(card_id='../escape')]
    with pytest.raises(ValueError,match='unsafe_stable_id'):
        render_run(store,'run-1',tmp_path/'output',PromptLoader(ASSETS))
    assert not (tmp_path/'escape').exists()


def test_report_links_actual_local_original_and_prompt_artifact(tmp_path,monkeypatch):
    monkeypatch.setattr('arc.budget.BudgetLedger',FakeLedger)
    store=FakeStore(tmp_path)
    store.artifact_root.mkdir()
    (store.artifact_root/'original.txt').write_text('Original material',encoding='utf-8')
    (store.artifact_root/'prompt.json').write_text('{}',encoding='utf-8')
    store.list_sources=lambda ids=None:[{'source_id':'s-1','title':'本地原文','url':None,'content_path':'original.txt'}]
    store.tasks[0]['rendered_prompt_path']='prompt.json'
    paths=render_run(store,'run-1',tmp_path/'output',PromptLoader(ASSETS))
    for key in ['overview','card:card-1:2','trace']:
        for target in re.findall(r'\]\(([^)]+)\)',paths[key].read_text(encoding='utf-8')):
            if not target.startswith('https://'):
                assert (paths[key].parent/unquote(target)).is_file()
    assert 'original.txt' in paths['card:card-1:2'].read_text(encoding='utf-8')
    assert 'prompt.json' in paths['trace'].read_text(encoding='utf-8')


@pytest.mark.parametrize('assessment,expected_main', [('PROMISING',1),('REJECTED',0),('NEEDS_EVIDENCE',0),(None,0)])
def test_later_stage_reports_final_assessment_instead_of_old_selection(tmp_path,monkeypatch,assessment,expected_main):
    monkeypatch.setattr('arc.budget.BudgetLedger',FakeLedger)
    store=FakeStore(tmp_path)
    store.cards=[card('MAIN_REPORT')]
    store.run.update(mode='run',card_id='card-1',card_version=2,assessment=assessment,
        state={'final_ruling':{'concise_ruling':'当前阶段发现新的致命混淆。','next_action':'STOP','decisive_evidence_ids':['e-1'],'external_test_requirements':['人类需执行明确的区分实验。']}})
    original=copy.deepcopy(store.cards)
    paths=render_run(store,'run-1',tmp_path/'output',PromptLoader(ASSETS))
    report=paths['overview'].read_text(encoding='utf-8')
    detail=paths['card:card-1:2'].read_text(encoding='utf-8')
    assert f'{expected_main} 张进入主报告' in report
    assert '当前阶段发现新的致命混淆。' in detail
    assert '已登记判断的原句' not in detail
    assert '人类需执行明确的区分实验。' in detail
    assert store.cards==original
    if assessment is None:
        assert '当前卡与未完成判断' in report


def test_developed_card_without_selection_is_shown_from_current_assessment(tmp_path,monkeypatch):
    monkeypatch.setattr('arc.budget.BudgetLedger',FakeLedger)
    store=FakeStore(tmp_path)
    old=card(); old['version']=1
    current=card(); current.update(selection=None,assessment=None,selection_result=None)
    store.cards=[old,current]
    store.run.update(mode='develop',card_id='card-1',card_version=2,assessment='PROMISING',state={'final_ruling':{'concise_ruling':'方案可以交给人执行最小检验。','next_action':'HANDOFF_EXPERIMENT'}})
    paths=render_run(store,'run-1',tmp_path/'output',PromptLoader(ASSETS))
    report=paths['overview'].read_text(encoding='utf-8')
    assert '1 张进入主报告' in report
    assert 'cards/card-1/v2.md' in report
    assert 'cards/card-1/v1.md' not in report
    assert '当前阶段科研判断：值得继续调查' in paths['card:card-1:2'].read_text(encoding='utf-8')
