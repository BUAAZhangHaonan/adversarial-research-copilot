"""Deterministic Chinese reports rebuilt from the authoritative store."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from arc.prompting import PromptLoader


LABELS = {
    'question':'研究问题','research_object':'研究对象','conditions':'适用条件','anti_scope':'范围限制',
    'primary_type':'主要增量类型','secondary_types':'其他增量类型','knowledge_increment':'增加的认识','decision_changed':'改变的研究决定',
    'observation_or_deficit':'观察或解释缺口','evidence_ids':'证据','unresolved_assumptions':'未核实假设',
    'source_ids':'来源','established_claim':'已有结论','remaining_claim':'新增主张','search_limits':'检索边界',
    'main_or_competing_explanations':'核心及竞争解释','distinct_predictions':'不同预测','favored_only_if_justified':'倾向解释的依据',
    'simplest_path':'最简路径','necessary_components':'必要成分','stitching_assessment':'组合必要性',
    'intervention':'改变什么','controls':'固定什么','measurements':'观察什么','positive_controls':'有效性检查',
    'outcome_interpretations':'不同结果如何解释','confounds_not_yet_ruled_out':'尚未排除的混淆因素',
    'gpu_type':'GPU类型','gpu_memory_gb_assumption':'每卡显存假设（GB）','gpu_count':'GPU数量',
    'training_gpu_hours_range':'训练GPU-hours','inference_gpu_hours_range':'推理GPU-hours','wall_hours_range':'墙钟时长（小时）',
    'workload_assumptions':'工作量假设','estimate_basis':'估计依据','uncertainty':'估计不确定性',
    'decisive_risks':'关键风险','missing_prerequisites':'缺失前提','reopen_conditions':'重开条件',
    'assessment':'科研判断','next_action':'下一步','reopening_condition':'重开条件','selection':'保留结论',
    'why_worth_investigating':'值得调查的理由','closest_work_delta':'最近工作的区别','resource_assessment':'资源判断',
    'lower':'下界','upper':'上界','unit':'单位','status':'状态','spent_lower_cny':'已结算下界（元）',
    'spent_upper_cny':'已结算上界（元）','reserved_cny':'预留（元）','remaining_cny':'剩余额度（元）',
    'limit_cny':'授权上限（元）','cost_status':'费用可信度','account_id':'预算账户','parent_id':'父级账户',
    'recorded_run_id':'证据登记运行',
}
SELECTIONS = {'MAIN_REPORT':'值得继续调查','LEAD_ONLY':'待补证线索','NOT_RETAINED':'本次不保留'}
ASSESSMENTS = {'PROMISING':'值得继续调查','NEEDS_EVIDENCE':'缺少判断所需证据','REJECTED':'已有依据不支持继续','SCOPE_CHANGE_PROPOSED':'建议转向，当前已冻结'}


def render_capability_handoff(record, loader=None, *, development_review=False):
    """A deterministic review/implementation handoff, never a task dispatch."""
    from .schemas import CapabilityRequest
    request={key:record[key] for key in CapabilityRequest.model_fields}
    return (loader or PromptLoader()).render_report('capability_handoff', {
        'record':record, 'request_json':json.dumps(request,ensure_ascii=False,indent=2),
        'review_json':json.dumps(record.get('review'),ensure_ascii=False,indent=2),
        'development_review':development_review,
    })


def _obj(value: Any) -> Any:
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    return value


def _text(value: Any) -> str:
    if value is None or value == '' or value == [] or value == {}:
        return '未记录'
    if isinstance(value, bool):
        return '是' if value else '否'
    if isinstance(value, list):
        return '；'.join(_text(item) for item in value)
    if isinstance(value, dict):
        return '\n\n'.join(f'{LABELS.get(key, key)}：{_text(item)}' for key, item in value.items())
    return str(value)


def _heading(value: Any) -> str:
    return re.sub(r'([\\`*_{}\[\]<>|#])', r'\\\1', str(value).replace('\n', ' ').replace('\r', ' '))


def _safe_id(value: Any) -> str:
    value = str(value)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value) or '..' in value:
        raise ValueError('unsafe_stable_id')
    return value


def _public_url(value: Any) -> str | None:
    if not value:
        return None
    parsed = urlsplit(str(value))
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.username or parsed.password:
        return None
    return quote(str(value), safe=':/?&=#%+-._~')


def _artifact_path(value: Any, output_dir: Path, store: Any) -> str | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = Path(store.artifact_root) / path
    if not path.is_file():
        return None
    return quote(Path(os.path.relpath(path.resolve(), output_dir.resolve())).as_posix(), safe='/.-_')


def _reference_ids(value: Any, keys: set[str]) -> set[str]:
    if isinstance(value, list):
        return set().union(*(_reference_ids(item, keys) for item in value))
    if not isinstance(value, dict):
        return set()
    found = set()
    for key, item in value.items():
        if key in keys:
            found.update(ref for ref in (item if isinstance(item, list) else [item]) if isinstance(ref, str))
        elif isinstance(item, (dict, list)):
            found.update(_reference_ids(item, keys))
    return found


EVIDENCE_KEYS = {'evidence_id', 'evidence_ids', 'anchor_evidence_ids', 'trigger_evidence_ids',
                 'decisive_evidence_ids', 'basis_evidence_ids', 'new_evidence_ids'}
SOURCE_KEYS = {'source_id', 'source_ids', 'target_source_ids', 'original_sources_revisited'}


def _source_links(source_ids: set[str], sources: list[dict], base_dir: Path, store: Any) -> list[dict]:
    return [{'id': _heading(s['source_id']), 'title': _heading(s.get('title') or s['source_id']), 'url': url}
            for s in sources if s['source_id'] in source_ids
            and (url := (_public_url(s.get('url')) or _artifact_path(s.get('content_path'), base_dir, store)))]


def _sources_for(card: dict, evidence: list[dict], sources: list[dict], base_dir: Path,
                 store: Any, issues: list[dict] = ()) -> list[dict]:
    references = [card, [issue for issue in issues if issue.get('card_id') in {None, card['card_id']}]]
    ids = _reference_ids(references, EVIDENCE_KEYS)
    source_ids = _reference_ids(references, SOURCE_KEYS)
    source_ids.update(e['source_id'] for e in evidence if e['evidence_id'] in ids)
    return _source_links(source_ids, sources, base_dir, store)


def _card_context(card: dict, sources: list[dict], issues: list[dict], *, focused_stage: bool = False,
                  claim_bindings: list[dict] = ()) -> dict:
    draft = card['draft']
    selection = card.get('selection')
    assessment = card.get('assessment')
    risks = draft.get('risks', {})
    judgment = card.get('selection_result') or {}
    anchor = draft['problem_anchor']
    hypothesis = draft.get('hypotheses', {})
    test = draft.get('minimal_test', {})
    unresolved = [issue for issue in issues if issue.get('card_id') in {None, card['card_id']}
                  and issue.get('status') not in {'resolved', 'withdrawn'}]
    decision = (f"当前阶段科研判断：{ASSESSMENTS.get(assessment, assessment or '尚未形成判断')}。" if focused_stage else
                f"当前结论：{SELECTIONS.get(selection, selection or '尚未形成保留判断')}。科研判断：{ASSESSMENTS.get(assessment, assessment or '尚未形成判断')}。")
    bindings_text = '\n'.join(
        f"- {_heading(b['claim_id'])} v{b['claim_version']} 引用 {_heading(b['evidence_id'])}：" +
        ('背景依据；原证据针对 ' + _heading(b['evidence_claim_id']) +
         f" v{b['evidence_claim_version']}，不转移验证状态。"
         if b['binding'] == 'background_premise' else
         '当前主张的定向证据；关联本身不表示主张已证实，仍需审查条件与支持关系。')
        for b in claim_bindings)
    return {
        'title': _heading(draft.get('title') or anchor['question']),
        'decision_paragraph': decision+'\n\n'+_text(judgment.get('why_worth_investigating')),
        'motivation_paragraph': _text(draft.get('motivation')) +
            ('\n\n主张与引用关系：\n\n' + bindings_text if bindings_text else ''),
        'knowledge_gain_paragraph': _text(draft.get('contribution')),
        'nearest_work_paragraph': _text(draft.get('closest_work_delta')),
        'hypothesis_paragraph': _text(hypothesis.get('main_or_competing_explanations')),
        'alternative_paragraph': _text({'distinct_predictions': hypothesis.get('distinct_predictions'), 'favored_only_if_justified':hypothesis.get('favored_only_if_justified')}),
        'test_paragraph': _text({key:test.get(key) for key in ['intervention','controls','measurements','positive_controls']})+'\n\n'+_text(draft.get('method')),
        'result_interpretation_paragraph': _text({key:test.get(key) for key in ['outcome_interpretations','confounds_not_yet_ruled_out']}),
        'resource_paragraph': _text(draft.get('resources')),
        'risks_paragraph': _text(judgment.get('decisive_risks',risks.get('decisive_risks'))),
        'unresolved_paragraph': _text({'missing_prerequisites':risks.get('missing_prerequisites'), 'unresolved_assumptions':draft.get('motivation',{}).get('unresolved_assumptions')}) + '\n\n' + '\n'.join(f"- {issue['issue_id']}（{issue['status']}）：{_text(issue.get('content', issue.get('dispute')))}" for issue in unresolved),
        'version_paragraph': f"研究卡 {card['card_id']}，版本 {card['version']}；原问题：{anchor['question']}。\n\n"+_text({'conditions':anchor.get('conditions'),'anti_scope':anchor.get('anti_scope')}),
        'next_step_paragraph': _text({'next_action':judgment.get('next_action'), 'external_test_requirements':judgment.get('external_test_requirements'), 'reopening_condition':judgment.get('reopening_condition'), 'reopen_conditions':risks.get('reopen_conditions')}),
        'sources':sources,
    }


def render_run(store: Any, run_id: str, output_dir: str | Path,
               prompt_loader: PromptLoader | None = None) -> dict[str, Path]:
    from arc.budget import BudgetLedger
    loader = prompt_loader or PromptLoader()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run = _obj(store.get_run(run_id))
    cards = [_obj(item) for item in store.list_cards(run_id=run_id)]
    focused_stage = run['mode'] in {'develop', 'run'}
    if focused_stage and run.get('card_id'):
        cards = [_obj(store.get_card(run['card_id'], run['card_version']))]
    issues = [_obj(item) for item in store.get_issues(run_id)]
    changes = [_obj(item) for item in store.list_direction_changes(run_id)]
    tasks = [_obj(item) for item in store.list_tasks(run_id)]
    capabilities = [_obj(item) for item in store.list_capability_requests(run_id)]
    state = run.get('state', {})
    references = [cards, issues, changes, {key: state.get(key) for key in
        ('evidence_ids', 'source_ids', 'final_ruling')},
        [{'evidence_ids': task.get('evidence_ids', [])} for task in tasks]]
    # Resolve inherited IDs without copying their records into the current run.
    # Frozen archive windows and rejected candidate payloads are not report evidence.
    evidence = [_obj(item) for item in store.list_evidence(
        ids=sorted(_reference_ids(references, EVIDENCE_KEYS)))]
    source_ids = _reference_ids(references, SOURCE_KEYS) | {e['source_id'] for e in evidence}
    sources = [_obj(item) for item in store.list_sources(ids=sorted(source_ids))]
    ledger = BudgetLedger(store.db_path)
    budget = ledger.summary(run['budget_account_id']) if run.get('budget_account_id') else None
    calls = ledger.list_calls(run['budget_account_id']) if run.get('budget_account_id') else []
    paths: dict[str, Path] = {}
    main, leads, rejected, pending_cards = [], [], [], []
    all_sources = {source['id']: source for source in _source_links(source_ids, sources, output_dir, store)}
    for card in cards:
        # A later stage owns its assessment. Never display a prior discovery
        # selection as approval of a revised proposal or a rejected review.
        card = dict(card)
        if focused_stage:
            card['selection'] = None
            card['assessment'] = run.get('assessment')
            ruling = run.get('state', {}).get('final_ruling') or {}
            card['selection_result'] = {
                'why_worth_investigating': ruling.get('concise_ruling'),
                'next_action': ruling.get('next_action'),
                'external_test_requirements': ruling.get('external_test_requirements'),
                'evidence_ids': ruling.get('decisive_evidence_ids', []),
                'reopening_condition': None,
            }
        category = card.get('selection') if not focused_stage else {
            'PROMISING': 'MAIN_REPORT', 'NEEDS_EVIDENCE': 'LEAD_ONLY', 'REJECTED': 'NOT_RETAINED',
        }.get(card.get('assessment'))
        relative = f"cards/{_safe_id(card['card_id'])}/v{int(card['version'])}.md"
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        related_sources = _sources_for(card,evidence,sources,target.parent,store,issues)
        context = _card_context(card, related_sources, issues, focused_stage=focused_stage,
                                claim_bindings=store.claim_evidence_bindings(card['draft']))
        target.write_text(loader.render_report('card',context),encoding='utf-8')
        paths[f"card:{card['card_id']}:{card['version']}"] = target
        if category == 'MAIN_REPORT':
            main.append({'title':context['title'],'decision_paragraph':context['decision_paragraph'],
                         'knowledge_gain_paragraph':context['knowledge_gain_paragraph'],
                         'main_risk_paragraph':context['risks_paragraph'],'relative_path':relative})
        elif category == 'LEAD_ONLY':
            leads.append({'title':context['title'],'missing_prerequisite_paragraph':context['unresolved_paragraph'],
                          'reopening_action_paragraph':context['next_step_paragraph']+f'\n\n[查看研究卡详情]({relative})'})
        elif category == 'NOT_RETAINED':
            rejected.append({'title':context['title'],'decision':context['decision_paragraph'],
                             'reopen':_text((card.get('selection_result') or {}).get('reopening_condition') or card['draft'].get('risks',{}).get('reopen_conditions')),'path':relative})
        else:
            pending_cards.append({'title':context['title'],'decision':context['decision_paragraph'],'path':relative})
    status = str(run['status'])
    cost_text = _text({key:value for key,value in budget.items() if not key.endswith('_micro')}) if budget else '费用账本未登记，费用未知。'
    pending = [task for task in tasks if task.get('status') != 'ACCEPTED']
    overview = {'report_title': f"ARC {_heading(run['mode'])} 研究总览",
                'executive_summary':f"当前执行状态：{status}。已保存 {len(cards)} 张研究卡，其中 {len(main)} 张进入主报告，{len(leads)} 张为待补证线索。科研判断：{ASSESSMENTS.get(run.get('assessment'), run.get('assessment') or '尚未形成')}。",
                'main_cards':main,'leads':leads,
                'scope_changes':[{'summary':_text(change.get('proposed_problem_anchor')),'original_evidence_audit':_text({'original_sources_revisited':change.get('original_sources_revisited'),'missed_evidence_analysis':change.get('missed_evidence_analysis'),'trigger_evidence_ids':change.get('trigger_evidence_ids')})} for change in changes],
                'scope_paragraph':_text({'run_id':run_id,'campaign_id':run.get('campaign_id'),'card_id':run.get('card_id'),'card_version':run.get('card_version')}),
                'execution_status_paragraph':f"执行状态：{status}；停止原因：{_text(run.get('stop_reason'))}。已保存任务 {len(tasks)} 项，未完成 {len(pending)} 项。",
                'cost_paragraph':cost_text,
                'next_step_paragraph':f"{'恢复命令' if status.startswith('PAUSED') else '查看状态'}：`arc {'resume' if status.startswith('PAUSED') else 'status'} {_safe_id(run_id)}`。阶段结束后的下一阶段需要显式选择与调用。",
                'sources':list(all_sources.values())}
    records={'rejected':rejected,'pending_cards':pending_cards,'pending_tasks':[{'id':t.get('task_id'),'status':t.get('status'),'reason':_text(t.get('error',t.get('error_code')))} for t in pending],
             'issues':[{'id':i['issue_id'],'status':i['status'],'content':_text(i.get('content',i.get('dispute'))),'criterion':_text(i.get('resolution_criterion',i.get('resolution_criteria'))),'change':_text(i.get('change_this_round'))} for i in issues]}
    report=loader.render_report('overview',overview)+'\n\n'+loader.render_report('records',records)
    paths['overview']=output_dir/'REPORT.md'
    paths['overview'].write_text(report,encoding='utf-8')
    trace_tasks=[]
    for task in tasks:
        artifacts=[]
        for key in ['rendered_prompt_path','response_artifact_path','environment_snapshot_path']:
            relative=_artifact_path(task.get(key),output_dir,store)
            if relative:
                artifacts.append({'label':key,'path':relative})
        if task.get('accepted_result') is not None:
            accepted_path=output_dir/'accepted'/f"{_safe_id(task['task_id'])}.json"
            accepted_path.parent.mkdir(parents=True,exist_ok=True)
            accepted_path.write_text(json.dumps(task['accepted_result'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            artifacts.append({'label':'已验收的结构化对象','path':accepted_path.relative_to(output_dir).as_posix()})
        trace_tasks.append({'id':task.get('task_id'),'status':task.get('status'),'identity':_text({key:task.get(key) for key in ['prompt_hash','model_id','attempt_ids']}),
                            'evidence':_text(task.get('evidence_ids',[])),'artifacts':artifacts})
    trace={'run_id':run_id,'tasks':trace_tasks,'evidence_records':[{'id':e['evidence_id'],'source_id':e['source_id'],'claim':e.get('claim'),
           'relation':e.get('relation'),'conditions':_text(e.get('conditions')),'locator':_text(e.get('locator')),
           'verification':_text({**{key:e.get(key) for key in ['origin','locator_status','verification_status']},
                                 'recorded_run_id':e.get('run_id')})} for e in evidence]}
    paths['trace']=output_dir/'PROMPT_TRACE_INDEX.md'
    paths['trace'].write_text(loader.render_report('trace',trace),encoding='utf-8')
    paths['cost']=output_dir/'COST_REPORT.md'
    cost_entries='\n\n'.join(_text({key:call.get(key) for key in ['call_id','account_id','status','cost_status','reserved_cny','cost_estimate_lower','cost_estimate_upper']}) for call in calls)
    paths['cost'].write_text(loader.render_report('cost',{'run_id':run_id,'summary':cost_text,'entries':cost_entries}),encoding='utf-8')
    if capabilities:
        paths['capabilities']=output_dir/'MCP_REQUIREMENTS.md'
        paths['capabilities'].write_text(loader.render_report('capabilities',{'run_id':run_id,'requests':[{'blocked_question':_heading(r['blocked_question']),'details':render_capability_handoff(r,loader)} for r in capabilities]}),encoding='utf-8')
    return paths
