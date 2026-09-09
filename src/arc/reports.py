"""Deterministic Chinese reports rebuilt from the authoritative store."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from arc.prompting import PromptLoader
from arc.research_context import EVIDENCE_KEYS, SOURCE_KEYS, reference_ids as _reference_ids


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
    'remaining_uncertainty':'仍未解决的科学问题','decisive_findings':'决定性审查发现',
    'location':'卡片位置','quoted_text':'被审查原句','reason':'依据','consequence':'对结论的影响',
    'required_change':'必要修改','acceptance_test':'复核条件','value_reason':'研究价值判断',
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
        return '\n\n'.join('- ' + _text(item) for item in value)
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
        'decision_paragraph': decision,
        'insight_paragraph': _text(draft.get('contribution', {}).get('knowledge_increment')),
        'motivation_paragraph': _text(draft.get('motivation', {}).get('observation_or_deficit')),
        'knowledge_gain_paragraph': _text({'decision_changed': draft.get('contribution', {}).get('decision_changed')}),
        'review_paragraph': _text(judgment.get('value_reason') or judgment.get('why_worth_investigating')),
        'bindings_paragraph': bindings_text,
        'nearest_work_paragraph': _text(draft.get('closest_work_delta')),
        'hypothesis_paragraph': _text(hypothesis.get('main_or_competing_explanations')),
        'alternative_paragraph': _text({'distinct_predictions': hypothesis.get('distinct_predictions'), 'favored_only_if_justified':hypothesis.get('favored_only_if_justified')}),
        'test_paragraph': _text({key:test.get(key) for key in ['intervention','controls','measurements','positive_controls']})+'\n\n'+_text(draft.get('method')),
        'result_interpretation_paragraph': _text({key:test.get(key) for key in ['outcome_interpretations','confounds_not_yet_ruled_out']}),
        'resource_paragraph': _text(draft.get('resources')),
        'risks_paragraph': _text(judgment.get('decisive_risks',risks.get('decisive_risks'))),
        'unresolved_paragraph': _text({'missing_prerequisites':risks.get('missing_prerequisites'), 'unresolved_assumptions':draft.get('motivation',{}).get('unresolved_assumptions'), 'remaining_uncertainty':judgment.get('remaining_uncertainty')}) +
            ('\n\n' + _text({'decisive_findings': judgment['decisive_findings']})
             if judgment.get('decisive_findings') else '') + '\n\n' + '\n'.join(f"- {issue['issue_id']}（{issue['status']}）：{_text(issue.get('content', issue.get('dispute')))}" for issue in unresolved),
        'version_paragraph': f"研究卡 {card['card_id']}，版本 {card['version']}；原问题：{anchor['question']}。\n\n"+_text({'conditions':anchor.get('conditions'),'anti_scope':anchor.get('anti_scope')}),
        'next_step_paragraph': _text({'next_action':judgment.get('next_action') or judgment.get('action'), 'external_test_requirements':judgment.get('external_test_requirements'), 'reopening_condition':judgment.get('reopening_condition'), 'reopen_conditions':risks.get('reopen_conditions')}),
        'sources':sources,
    }


def render_run(store: Any, run_id: str, output_dir: str | Path,
               prompt_loader: PromptLoader | None = None) -> dict[str, Path]:
    from arc.budget import BudgetLedger
    loader = prompt_loader or PromptLoader()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run = _obj(store.get_run(run_id))
    if run.get('state', {}).get('discover_first'):
        return render_discovery_run(store, run_id, output_dir, loader)
    cards = [_obj(item) for item in store.list_cards(run_id=run_id)]
    focused_stage = run['mode'] in {'develop', 'run'}
    if focused_stage and run.get('card_id'):
        cards = [_obj(store.get_card(run['card_id'], run['card_version']))]
    issues = [_obj(item) for item in store.get_issues(run_id)]
    changes = [_obj(item) for item in store.list_direction_changes(run_id)]
    tasks = [_obj(item) for item in store.list_tasks(run_id)]
    capabilities = [_obj(item) for item in store.list_capability_requests(run_id)]
    state = run.get('state', {})
    scientific_final = state.get('final_scientific_review')
    scientific_final_current = (scientific_final is not None and
        state.get('final_scientific_card_version') == run.get('card_version'))
    references = [cards, issues, changes,
                  scientific_final if scientific_final_current else
                  state.get('final_ruling') if scientific_final is None else None]
    trace_references = [references, {'evidence_ids': state.get('evidence_ids', [])},
                        [{'evidence_ids': task.get('evidence_ids', [])} for task in tasks]]
    # Resolve inherited IDs without copying their records into the current run.
    # Frozen archive windows and rejected candidate payloads are not report evidence.
    evidence = [_obj(item) for item in store.list_evidence(
        ids=sorted(_reference_ids(trace_references, EVIDENCE_KEYS)))]
    source_ids = _reference_ids(references, SOURCE_KEYS) | {e['source_id'] for e in evidence}
    formal_evidence_ids = _reference_ids(references, EVIDENCE_KEYS)
    formal_source_ids = _reference_ids(references, SOURCE_KEYS) | {
        e['source_id'] for e in evidence if e['evidence_id'] in formal_evidence_ids}
    sources = [_obj(item) for item in store.list_sources(ids=sorted(source_ids))]
    ledger = BudgetLedger(store.db_path)
    budget = ledger.summary(run['budget_account_id']) if run.get('budget_account_id') else None
    calls = ledger.list_calls(run['budget_account_id']) if run.get('budget_account_id') else []
    paths: dict[str, Path] = {}
    main, leads, rejected, pending_cards = [], [], [], []
    latest_versions = {card['card_id']: max(item['version'] for item in cards if item['card_id'] == card['card_id']) for card in cards}
    all_sources = {source['id']: source for source in _source_links(formal_source_ids, sources, output_dir, store)}
    for card in cards:
        # A later stage owns its assessment. Never display a prior discovery
        # selection as approval of a revised proposal or a rejected review.
        card = dict(card)
        if focused_stage:
            card['selection'] = None
            if scientific_final is not None:
                # A reviewed earlier version is not approval of the current card.
                card['assessment'] = run.get('assessment') if scientific_final_current else None
                card['selection_result'] = ({**scientific_final,
                    'next_action': state.get('next_action')} if scientific_final_current else {})
            else:
                card['assessment'] = run.get('assessment')
                ruling = state.get('final_ruling') or {}
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
        card_evidence_ids = _reference_ids([card, [i for i in issues if i.get('card_id') in {None, card['card_id']}]], EVIDENCE_KEYS)
        context['evidence_notes'] = [
            {'id': _heading(e['evidence_id']), 'source_id': _heading(e['source_id']),
             'excerpt': _text(e.get('excerpt')), 'locator': _text(e.get('locator')),
             'conditions': _text(e.get('conditions')), 'relation': e.get('relation'),
             'support_explanation': _text(e.get('support_explanation'))}
            for e in evidence if e['evidence_id'] in card_evidence_ids]
        target.write_text(loader.render_report('card',context),encoding='utf-8')
        paths[f"card:{card['card_id']}:{card['version']}"] = target
        # Keep every saved version's detail, but summarize each candidate once
        # using only its latest version's recorded judgment.
        if card['version'] != latest_versions[card['card_id']]:
            continue
        if category == 'MAIN_REPORT':
            main.append({'title':context['title'],'decision_paragraph':context['decision_paragraph'],
                         'insight_paragraph':context['insight_paragraph'],
                         'motivation_paragraph':context['motivation_paragraph'],
                         'knowledge_gain_paragraph':context['knowledge_gain_paragraph'],
                         'main_risk_paragraph':context['risks_paragraph'],'relative_path':relative})
        elif category == 'LEAD_ONLY':
            judgment = card.get('selection_result') or {}
            current_risks = [item.get('consequence') or item.get('reason')
                for item in judgment.get('decisive_findings', [])]
            if not current_risks:
                current_risks = (judgment.get('decisive_risks') or card['draft'].get('risks', {}).get('decisive_risks') or [])[:1]
            leads.append({'title':context['title'], 'decision_paragraph':context['decision_paragraph'],
                          'insight_paragraph':context['insight_paragraph'],
                          'knowledge_gain_paragraph':context['knowledge_gain_paragraph'],
                          'main_risk_paragraph':_text(current_risks),
                          'missing_prerequisite_paragraph':context['unresolved_paragraph'],
                          'reopening_action_paragraph':context['next_step_paragraph']+f'\n\n[查看研究卡详情]({relative})'})
        elif category == 'NOT_RETAINED':
            if card['version'] == latest_versions[card['card_id']]:
                judgment = card.get('selection_result') or {}
                corrections = [
                    ('复核已解决：' if item.get('status') == 'resolved' else '复核撤回先前判断：') + _text(item.get('reason'))
                    for item in judgment.get('prior_findings', []) if item.get('status') in {'resolved', 'reviewer_error'}]
                rejected.append({'title':context['title'],'decision':context['decision_paragraph'],
                    'reason':_text(judgment.get('value_reason') or judgment.get('why_worth_investigating') or
                                   f"当前决策为 {judgment.get('action', '不保留')}，尚未记录具体价值理由。"),
                    'corrections':corrections,
                    'defects':[{'location':item.get('location'), 'reason':item.get('reason'),
                                'required_change':item.get('required_change')}
                               for item in judgment.get('decisive_findings', [])],
                    'reopen':_text(judgment.get('reopening_condition') or card['draft'].get('risks',{}).get('reopen_conditions')),'path':relative})
        else:
            pending_cards.append({'title':context['title'],'decision':context['decision_paragraph'],'path':relative})
    status = str(run['status'])
    cost_text = _text({key:value for key,value in budget.items() if not key.endswith('_micro')}) if budget else '费用账本未登记，费用未知。'
    superseded = {item['source_task_id'] for attempts in state.get('task_retries', {}).values()
                  for item in attempts}
    accepted = {task['task_id'] for task in tasks if task.get('status') == 'ACCEPTED'}
    for key, recheck in state.items():
        if (key.endswith('_source_recheck') and isinstance(recheck, dict)
                and key.removesuffix('_source_recheck') in state
                and recheck.get('replacement_task_id') in accepted):
            superseded.add(recheck.get('rejected_task_id'))
    historical = [task for task in tasks if task.get('status') != 'ACCEPTED'
                  and (status == 'COMPLETED' or task.get('task_id') in superseded)]
    historical_ids = {task['task_id'] for task in historical}
    pending = [task for task in tasks if task.get('status') != 'ACCEPTED'
               and task.get('task_id') not in historical_ids]
    historical_details = ''
    if historical:
        historical_details = '\n\n### 历史失败与未验收记录（保留审计）\n\n' + '\n'.join(
            f"- [{_heading(task['task_id'])}](PROMPT_TRACE_INDEX.md)：{task.get('status')}；"
            f"{_text(task.get('error', task.get('error_code')))}。原任务保留；"
            f"{'已由后续任务接替' if task['task_id'] in superseded else '所属阶段已完成'}，不计入当前未完成任务。"
            for task in historical)
    overview = {'report_title': f"ARC {_heading(run['mode'])} 研究总览",
                'executive_summary':f"本次已保存 {len(latest_versions)} 张候选研究卡（共 {len(cards)} 个保存版本），其中 {len(main)} 张进入主报告，{len(leads)} 张为待补证线索。以下是当前候选的认识与风险；保留判断不代表假设已被实验验证。",
                'main_cards':main,'leads':leads,'rejected':rejected,
                'scope_changes':[{'summary':_text(change.get('proposed_problem_anchor')),'original_evidence_audit':_text({'original_sources_revisited':change.get('original_sources_revisited'),'missed_evidence_analysis':change.get('missed_evidence_analysis'),'trigger_evidence_ids':change.get('trigger_evidence_ids')})} for change in changes],
                'scope_paragraph':_text({'run_id':run_id,'campaign_id':run.get('campaign_id'),'card_id':run.get('card_id'),'card_version':run.get('card_version')}),
                'execution_status_paragraph':f"执行状态：{status}；停止原因：{_text(run.get('stop_reason'))}。已保存任务 {len(tasks)} 项，当前未完成 {len(pending)} 项，历史失败与未验收记录 {len(historical)} 项。" + historical_details,
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
    # Preserve the full search trail in an explicitly separate audit appendix.
    # Membership here never promotes a hit into a research citation.
    encountered_ids = set(state.get('source_ids', []))
    encountered_sources = [_obj(item) for item in store.list_sources(ids=sorted(encountered_ids))]
    paths['search_sources'] = output_dir / 'SEARCH_SOURCES.md'
    search_lines = ['# 检索命中审计', '',
                    '此处记录检索过程中遇到的来源，不表示相关、已读或支持当前结论。正式引用见研究报告。', '']
    for source in encountered_sources:
        links = _source_links({source['source_id']}, [source], output_dir, store)
        label = _heading(source['source_id']) + '：' + _heading(source.get('title', ''))
        search_lines.append(f"- [{label}]({links[0]['url']})" if links else '- ' + label)
    paths['search_sources'].write_text('\n'.join(search_lines) + '\n', encoding='utf-8')
    paths['cost']=output_dir/'COST_REPORT.md'
    cost_entries='\n\n'.join(_text({key:(call.get('state', call.get('status')) if key == 'status' else call.get(key))
        for key in ['call_id','account_id','status','cost_status','reserved_cny','cost_estimate_lower','cost_estimate_upper']}) for call in calls)
    paths['cost'].write_text(loader.render_report('cost',{'run_id':run_id,'summary':cost_text,'entries':cost_entries}),encoding='utf-8')
    if capabilities:
        paths['capabilities']=output_dir/'MCP_REQUIREMENTS.md'
        paths['capabilities'].write_text(loader.render_report('capabilities',{'run_id':run_id,'requests':[{'blocked_question':_heading(r['blocked_question']),'details':render_capability_handoff(r,loader)} for r in capabilities]}),encoding='utf-8')
    return paths


DISCOVERY_ACCESS = {'metadata': '元数据', 'abstract': '摘要', 'passage': '定向段落',
                    'full_text': '全文', 'code': '代码', 'secondary': '二手材料'}
DISCOVERY_DECISIONS = {'discuss': '值得讨论', 'lead': '有条件线索', 'drop': '本次放下'}


def _discovery_sources(ids, notes, sources, output_dir, store):
    by_id = {source['source_id']: source for source in sources}
    note_by_id = {note['source_id']: note for note in notes}
    result = []
    for source_id in dict.fromkeys(ids):
        source = by_id.get(source_id, {})
        note = note_by_id.get(source_id, {})
        access = DISCOVERY_ACCESS.get(note.get('access'), '阅读层级未记录')
        if note.get('limits'):
            access += '；' + note['limits']
        result.append({'id': source_id, 'title': _heading(source.get('title') or source_id),
                       'url': _public_url(source.get('url')) or _artifact_path(source.get('content_path'), output_dir, store),
                       'finding': note.get('finding', '未记录材料摘记'),
                       'relevance': note.get('relevance', '候选引用；未记录来源笔记'), 'access_text': access})
    return result


def _discovery_usage(store, tasks, calls):
    tools, unavailable = 0, 0
    for task in tasks:
        path = task.get('response_artifact_path')
        if not path:
            continue
        try:
            state = json.loads(store.read_artifact(path))
            tools += len(state.get('tool_trace', []))
        except (OSError, ValueError, KeyError):
            unavailable += 1
    requests = [call for call in calls if not call.get('tool_call_id')
                and not (call.get('metadata') or {}).get('tool_call_id')
                and (call.get('started_at') or call.get('state') in {'SETTLED', 'UNKNOWN'})
                and call.get('state') != 'NOT_SENT']
    counts = {'semantic_tasks': len(tasks), 'model_requests': len(requests), 'tool_actions': tools,
              'tool_trace_unavailable_tasks': unavailable}
    for field in ['input_tokens', 'completion_tokens']:
        values = [call.get(field) for call in requests]
        counts[field] = sum(value for value in values if value is not None)
        counts[field + '_missing_requests'] = sum(value is None for value in values)
    return counts


def render_discovery_run(store: Any, run_id: str, output_dir: str | Path,
                         prompt_loader: PromptLoader | None = None) -> dict[str, Path]:
    """Publish saved lightweight objects; never construct a card or invoke a model."""
    from arc.budget import BudgetLedger
    loader = prompt_loader or PromptLoader()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run = _obj(store.get_run(run_id))
    state = run.get('state', {})
    ideas = [_obj(idea) for idea in store.list_discovery_ideas(run_id=run_id)]
    selected = state.get('idea_input') or {}
    brief = state.get('field_brief') or selected.get('field_brief') or {}
    topic = (store.get_campaign(run['campaign_id']).topic if run.get('campaign_id') else selected.get('original_question', ''))
    if selected:
        original = _obj(store.get_discovery_idea(selected['idea_id']))
        # A prior discovery recommendation is not acceptance of this stage.
        ideas = [{**original, 'seed': selected['seed'], 'note': state.get('prestudy_note'),
                  'triage': None, 'status': 'checked' if state.get('prestudy_note') else 'pending'}]
    tasks = [_obj(task) for task in store.list_tasks(run_id)]
    ledger = BudgetLedger(store.db_path)
    account = run.get('budget_account_id')
    budget = ledger.summary(account) if account else None
    calls = ledger.list_calls(account) if account else []
    cost_text = (_text({key: value for key, value in budget.items() if not key.endswith('_micro')})
                 if budget else '费用账本未登记，费用未知。')
    all_ids = set(state.get('source_ids', [])) | _reference_ids([brief, ideas], SOURCE_KEYS)
    sources = [_obj(source) for source in store.list_sources(ids=sorted(all_ids))]
    paths: dict[str, Path] = {}
    discuss, leads, skipped, pending = [], [], [], []
    field_notes = brief.get('source_notes', [])
    for idea in ideas:
        note, triage = idea.get('note') or {}, idea.get('triage') or {}
        seed = note.get('seed') or idea.get('seed')
        if seed is None:
            skipped.append({'title': '未提交候选', 'reason': idea.get('reason') or (idea.get('sketch') or {}).get('reason') or triage.get('reason') or idea.get('status', '未记录'), 'path': None})
            continue
        idea_id = _safe_id(idea['idea_id'])
        relative = f'ideas/{idea_id}.md'
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        note_ids = _reference_ids([seed, note], SOURCE_KEYS)
        source_notes = field_notes + note.get('source_notes', [])
        references = _discovery_sources(sorted(note_ids), source_notes, sources, target.parent, store)
        provenance = (f"想法 `{idea_id}`；运行 `{_safe_id(run_id)}`；抽卡机会 {idea.get('draw_id', '未记录')}；"
                      f"资料版本 {idea.get('brief_version', '未记录')}。原题：{idea.get('topic', '')}")
        context = {'title': _heading(seed['title']), 'insight': seed['insight'],
                   'why_it_matters': seed['why_it_matters'], 'sources': references,
                   'provenance_line': provenance}
        reason = note.get('reason') or triage.get('reason') or '已保存灵感，等待价值筛选或候选预研'
        item = {'title': context['title'], 'insight': seed['insight'], 'reason': reason,
                'risk': note.get('main_risk') or seed['key_unknown'], 'path': relative}
        if note:
            decision = note['decision']
            nearest = '\n\n'.join(
                f"- {work['source_id']}：已做到 {work['already_established']}；剩余差异：{work['remaining_difference']}。"
                + (f" 待查：{work['uncertainty']}" if work.get('uncertainty') else '')
                for work in note.get('nearest_work', []))
            resources = note.get('resources') or {}
            resource_fields = {'GPU': resources.get('gpu_type'), '数量': resources.get('gpu_count'),
                               '训练时长粗估': resources.get('training_hours_estimate'),
                               '推理时长粗估': resources.get('inference_hours_estimate'), '依据与未知': resources.get('basis')}
            context.update(status_text=DISCOVERY_DECISIONS[decision] + '：' + reason,
                           literature_paragraph=nearest or '尚未形成足够的近邻比较，不能据此宣称不存在重复。',
                           feasibility_paragraph=note['feasibility'], resource_paragraph=_text(resource_fields),
                           main_risk=note['main_risk'], limits_paragraph=_text(note.get('limits', [])),
                           next_question=note['next_question'], changes=_text(note['changes_from_seed']) if note.get('changes_from_seed') else '')
            target.write_text(loader.render_report('discovery_idea', context), encoding='utf-8')
            {'discuss': discuss, 'lead': leads, 'drop': skipped}[decision].append(item)
        else:
            status = {'park': '暂存线索，未做定向预研', 'drop': '初筛放下，未做定向预研'}.get(idea.get('status'), '待预研')
            context.update(status_text=status, question=seed['question'], difference=seed['difference_from_known'],
                           reason=reason, unknown=seed['key_unknown'], questions=_text(triage.get('check_questions', [])))
            target.write_text(loader.render_report('discovery_pending', context), encoding='utf-8')
            (leads if idea.get('status') == 'park' else skipped if idea.get('status') == 'drop' else pending).append(item)
        paths['idea:' + idea_id] = target
    # Non-submissions consume a draw but do not invent an IdeaSeed.
    for direction in state.get('previous_directions', []):
        if direction.get('action') in {'skip', 'stop'}:
            skipped.append({'title': direction.get('title', '未提交候选'),
                            'reason': direction.get('reason', ''), 'path': None})
    paths['field_brief'] = output_dir / 'FIELD_BRIEF.md'
    paths['field_brief'].write_text(loader.render_report('discovery_field', {
        'original_topic': topic or (ideas[0].get('topic', '') if ideas else state.get('original_task', '')),
        'overview': brief.get('overview', '领域调查尚未完成。'), 'research_lines': _text(brief.get('research_lines', [])),
        'openings': _text(brief.get('openings', [])), 'search_limits': _text(brief.get('search_limits', [])),
        'sources': _discovery_sources([note['source_id'] for note in field_notes], field_notes, sources, output_dir, store),
    }), encoding='utf-8')
    usage = _discovery_usage(store, tasks, calls)
    usage.update(first_seed_at=state.get('first_seed_at'), first_note_at=state.get('first_note_at'))
    paths['usage'] = output_dir / 'DISCOVERY_USAGE.json'
    paths['usage'].write_text(json.dumps(usage, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if selected:
        paths['input_idea'] = output_dir / 'INPUT_IDEA.json'
        paths['input_idea'].write_text(json.dumps(selected, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    paths['overview'] = output_dir / 'REPORT.md'
    paths['overview'].write_text(loader.render_report('discovery_overview', {
        'report_title': {'develop': '已选想法的预研展开', 'run': '已选想法的压力讨论'}.get(run['mode'], '本次发现'),
        'conclusion': f"已保存 {sum(idea.get('seed') is not None for idea in ideas)} 个想法：{len(discuss)} 个值得讨论，{len(leads)} 条线索，{len(pending)} 个待预研。建议由人选择，不代表科学认证。",
        'landscape_summary': brief.get('overview', '领域调查尚未完成。'), 'discuss': discuss, 'leads': leads,
        'skipped': skipped, 'pending': pending,
        'investigation_scope': ('[本阶段收到的想法和此前预研](INPUT_IDEA.json)；' if selected else '') + '[共享领域调查与阅读边界](FIELD_BRIEF.md)；[全部检索命中](SEARCH_SOURCES.md)；[原始任务索引](PROMPT_TRACE_INDEX.md)。',
        'cost_summary': cost_text + f"\n\n语义任务 {usage['semantic_tasks']} 项；实际模型请求 {usage['model_requests']} 次；工具动作 {usage['tool_actions']} 次。"
                        + '\n\n[调用、token 与首个产物时间](DISCOVERY_USAGE.json)。',
        'stop_reason': f"执行状态：{run['status']}；停止原因：{_text(run.get('stop_reason'))}。预算或工具暂停不等于否定想法。",
        'next_stage_instruction': f"先由人选择想法，再显式调用 develop 或 run。{'恢复本次：`arc resume ' + _safe_id(run_id) + '`。' if str(run['status']).startswith('PAUSED') else ''}",
    }), encoding='utf-8')
    paths['search_sources'] = output_dir / 'SEARCH_SOURCES.md'
    paths['search_sources'].write_text(loader.render_report('discovery_search', {
        'sources': _discovery_sources(sorted(set(state.get('source_ids', []))), [], sources, output_dir, store)
    }), encoding='utf-8')
    trace_tasks = []
    for task in tasks:
        artifacts = []
        for key in ['rendered_prompt_path', 'response_artifact_path', 'environment_snapshot_path']:
            if relative := _artifact_path(task.get(key), output_dir, store):
                artifacts.append({'label': key, 'path': relative})
        if task.get('accepted_result') is not None:
            accepted_path = output_dir / 'accepted' / f"{_safe_id(task['task_id'])}.json"
            accepted_path.parent.mkdir(parents=True, exist_ok=True)
            accepted_path.write_text(json.dumps(task['accepted_result'], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            artifacts.append({'label': '已保存的结构化对象', 'path': accepted_path.relative_to(output_dir).as_posix()})
        trace_tasks.append({'id': task['task_id'], 'status': task['status'],
                            'identity': _text({key: task.get(key) for key in ['model_id', 'attempt_ids']}),
                            'evidence': _text(task.get('evidence_ids', [])), 'artifacts': artifacts})
    paths['trace'] = output_dir / 'PROMPT_TRACE_INDEX.md'
    paths['trace'].write_text(loader.render_report('trace', {'run_id': run_id, 'tasks': trace_tasks, 'evidence_records': []}), encoding='utf-8')
    paths['cost'] = output_dir / 'COST_REPORT.md'
    entries = '\n\n'.join(_text({key: call.get(key) for key in ['call_id', 'state', 'cost_status', 'reserved_cny', 'cost_estimate_lower', 'cost_estimate_upper']}) for call in calls)
    paths['cost'].write_text(loader.render_report('cost', {'run_id': run_id, 'summary': cost_text, 'entries': entries}), encoding='utf-8')
    capabilities = store.list_capability_requests(run_id)
    if capabilities:
        paths['capabilities'] = output_dir / 'MCP_REQUIREMENTS.md'
        paths['capabilities'].write_text(loader.render_report('capabilities', {'run_id': run_id,
            'requests': [{'blocked_question': _heading(item['blocked_question']),
                          'details': render_capability_handoff(item, loader)} for item in capabilities]}), encoding='utf-8')
    return paths
