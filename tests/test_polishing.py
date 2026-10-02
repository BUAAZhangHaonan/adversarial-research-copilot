from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from arc.polishing import MAX_CITED_SOURCES, StagePolish, build_polish_payload, compact_polish_payload, validate_polish
from arc.prompting import PromptLoader, render_repair
from arc.reports import render_run
from .test_discovery_reports import Store, note, ASSETS


def prepared_store(tmp_path):
    store = Store(tmp_path)
    store.run.update(status='COMPLETED', stop_reason='human_selection')
    store.ideas[0].update(note=note(), status='checked')
    store.ideas[0]['note']['current_understanding'] = {
        'core_insight': '信息进入决策的时机可能影响选择。', 'invalidated_premises': [],
        'decisive_unknown': '时机是否提供额外决策价值。',
        'why_existing_insufficient': '当前材料提供信息覆盖的起点，时机问题仍需比较。'}
    return store


def written():
    return {'stage_summary': '这次预研关注信息是否在适当时机参与决策。现有材料支持继续讨论，但不能证明因果关系。',
            'overview': '近邻工作主要关注信息覆盖，也就是系统是否取得了任务所需材料。当前想法进一步询问信息进入行动的时机。',
            'candidates': [{'idea_id': 'i1', 'text': '核心想法是比较信息抵达与决策发生的关系。它仍然只是假设，任务难度可能同时影响二者。',
                            'cited_source_ids': ['s1', 's2']}], 'cited_source_ids': ['s2']}


def test_payload_uses_current_objects_and_deduplicates_source_notes(tmp_path):
    store = prepared_store(tmp_path)
    duplicate = store.run['state']['field_brief']['source_notes'][0]
    store.ideas[0]['note']['source_notes'].append(copy.deepcopy(duplicate))
    before = copy.deepcopy(store.__dict__)
    payload = build_polish_payload(store, 'r1')
    assert store.__dict__ == before
    assert {source['source_id'] for source in payload['source_directory']} == {'s1', 's2'}
    assert len(next(source for source in payload['source_directory'] if source['source_id'] == 's1')['notes']) == 1
    assert 'field_brief' not in payload
    assert 'note' not in payload['candidates'][0]
    assert payload['candidates'][0]['technical_context']['limits'] == note()['limits']
    assert payload['candidates'][0]['technical_context']['risk_analysis'] == note()['main_risk']
    assert payload['candidates'][0]['decision'] == 'discuss'
    assert 'seed' not in payload['candidates'][0]  # Original remains in the stored technical note.
    assert 'noise' not in json.dumps(payload)


def test_writer_view_keeps_proposal_distinct_from_source_result_and_old_endorsement(tmp_path):
    store = prepared_store(tmp_path)
    original_note = store.ideas[0]['note']
    original_note['reason'] = 'UNVERIFIED_ENDORSEMENT_MARKER'
    original_note['resources']['basis'] = 'RESOURCE_DETAIL_MARKER'
    work = original_note['nearest_work'][0]
    work['already_established'] = '来源报道版本通知后可更新。'
    work['brief_result'] = '来源使用版本通知更新记录。'
    work['remaining_difference'] = '候选猜想没有版本通知时仍能更新。'
    before = copy.deepcopy(store.__dict__)
    payload = build_polish_payload(store, 'r1')
    view = payload['candidates'][0]['writing_brief']
    assert view['source_summaries'][0]['reported_result'] == work['brief_result']
    assert payload['candidates'][0]['technical_context']['comparison_claims'][0]['remaining_difference'] == work['remaining_difference']
    assert view['source_summaries'][0]['source_id'] == work['source_id']
    assert 'UNVERIFIED_ENDORSEMENT_MARKER' not in json.dumps(payload)
    assert 'RESOURCE_DETAIL_MARKER' not in json.dumps(payload)
    assert store.__dict__ == before
    assert compact_polish_payload(payload) == payload


def test_pending_writer_view_retains_question_and_explicit_material_limits(tmp_path):
    store = prepared_store(tmp_path)
    store.ideas[0]['note'] = None
    store.ideas[0]['status'] = 'pending'
    before = copy.deepcopy(store.__dict__)
    payload = build_polish_payload(store, 'r1')
    view = payload['candidates'][0]['writing_brief']
    assert view['proposal']['question'] == store.ideas[0]['seed']['question']
    assert view['decisive_unknown'] == store.ideas[0]['seed']['key_unknown']
    assert not view['source_summaries']
    assert payload['candidates'][0]['decision'] != 'discuss'
    assert store.__dict__ == before


def test_historical_writer_input_keeps_audit_identity_without_old_scientific_claims(tmp_path):
    store = prepared_store(tmp_path)
    old_note = store.ideas[0]['note']
    old_note.pop('current_understanding')
    for key in ['reason', 'main_risk', 'next_question', 'feasibility']:
        old_note[key] = 'HISTORICAL_FALSE_MARKER_' + key
    old_note['seed']['insight'] = 'HISTORICAL_FALSE_MARKER_insight'
    for work in old_note['nearest_work']:
        work['already_established'] = 'HISTORICAL_FALSE_MARKER_source'
        work['remaining_difference'] = 'HISTORICAL_FALSE_MARKER_novelty'
    before = copy.deepcopy(store.__dict__)
    payload = build_polish_payload(store, 'r1')
    assert 'HISTORICAL_FALSE_MARKER' not in json.dumps(payload)
    view = payload['candidates'][0]
    assert view['writing_brief']['proposal']['review_status'] == 'historical_note_requires_current_review'
    assert view['technical_context']['audit_reference']['idea_id'] == 'i1'
    assert store.__dict__ == before


def test_writer_uses_current_source_brief_and_keeps_long_source_detail_in_store(tmp_path):
    store = prepared_store(tmp_path)
    work = store.ideas[0]['note']['nearest_work'][0]
    work['already_established'] = 'LONG_TECHNICAL_DETAIL_MARKER' * 1000
    work['brief_result'] = 'The method predicts need and steers selection.'
    store.ideas[0]['note']['current_understanding']['illustrative_example'] = 'An explicitly labeled paired-goal example.'
    before = copy.deepcopy(store.__dict__)
    payload = build_polish_payload(store, 'r1')
    assert 'LONG_TECHNICAL_DETAIL_MARKER' not in json.dumps(payload)
    assert payload['candidates'][0]['writing_brief']['source_summaries'][0]['reported_result'] == work['brief_result']
    assert payload['candidates'][0]['writing_brief']['example'] == 'An explicitly labeled paired-goal example.'
    assert store.__dict__ == before


@pytest.mark.parametrize('change,problem', [
    (lambda result: result.update(candidates=[]), 'COVERAGE'),
    (lambda result: result['candidates'].append(copy.deepcopy(result['candidates'][0])), 'COVERAGE'),
    (lambda result: result.update(cited_source_ids=['noise']), 'SOURCE_OUTSIDE_DIRECTORY'),
    (lambda result: result['candidates'][0].update(cited_source_ids=['noise']), 'CANDIDATE_SOURCE'),
])
def test_polish_cannot_change_candidate_set_or_reference_directory(tmp_path, change, problem):
    store = prepared_store(tmp_path)
    result = written()
    change(result)
    with pytest.raises(ValueError, match=problem):
        validate_polish(result, build_polish_payload(store, 'r1'))


def test_candidate_cannot_borrow_another_candidates_reference(tmp_path):
    payload = build_polish_payload(prepared_store(tmp_path), 'r1')
    payload['candidates'][0]['source_ids'] = ['s1']
    with pytest.raises(ValueError, match='CANDIDATE_SOURCE'):
        validate_polish(written(), payload)


def test_normal_numeric_rephrasing_is_not_a_new_protocol_block(tmp_path):
    payload = build_polish_payload(prepared_store(tmp_path), 'r1')
    payload['candidates'][0]['technical_context']['proposed_entry'] = '原稿假设阈值0.95，仍需人检查。'
    result = written()
    result['candidates'][0]['text'] = '阈值为95%，仍需人检查。'
    assert validate_polish(result, payload).candidates[0].text == result['candidates'][0]['text']
    result['candidates'][0]['decision'] = 'discuss'
    with pytest.raises(ValidationError):
        StagePolish.model_validate(result)


def test_final_polished_report_preserves_technical_draft_and_authoritative_decision(tmp_path):
    store = prepared_store(tmp_path)
    store.ideas[0]['note']['decision'] = 'lead'
    store.run['state']['polish'] = written()
    before = copy.deepcopy(store.__dict__)
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    report = paths['overview'].read_text()
    detail = paths['idea:i1'].read_text()
    technical = paths['technical_overview'].read_text()
    assert written()['stage_summary'] in report and written()['overview'] in report
    assert written()['candidates'][0]['text'] in detail
    assert '有条件线索' in report and '有条件线索' in detail
    assert 'https://example.org/s2' in report and 'https://example.org/s1' in detail
    assert 'noise' not in report + detail
    assert '修改与材料记录' in paths['technical_idea:i1'].read_text()
    assert note()['changes_from_seed'][0] in paths['technical_idea:i1'].read_text()
    assert 'ideas/i1.technical.md' in technical
    assert '[预研记录](TECHNICAL_REPORT.md)' in report and 'i1.technical.md' in detail
    assert 'COMPLETED' not in report and 'human_selection' not in report
    assert '（s2）' not in report
    assert '本阶段已完成，是否继续由人决定' in report
    assert store.__dict__ == before
    # A rebuild must not accidentally archive polished prose as the original technical view.
    again = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    assert again['technical_overview'].read_text() == technical


def test_unpolished_history_remains_explicitly_technical(tmp_path):
    store = prepared_store(tmp_path)
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    assert '当前为技术稿，尚无已接受的最终润色' in paths['overview'].read_text()
    assert '修改与材料记录' in paths['technical_idea:i1'].read_text()
    assert note()['changes_from_seed'][0] in paths['technical_idea:i1'].read_text()
    assert 'polish' not in store.run['state']


def test_empty_stage_polishes_without_inventing_candidates(tmp_path):
    store = prepared_store(tmp_path)
    store.ideas = []
    result = written()
    result['candidates'] = []
    result['cited_source_ids'] = ['s1']
    store.run['state']['polish'] = result
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    assert '没有已保存的候选灵感' in paths['overview'].read_text()
    assert not any(key.startswith('idea:') for key in paths)


def test_prestudy_writer_receives_current_stage_note_not_old_recommendation(tmp_path):
    store = prepared_store(tmp_path)
    store.original_idea = copy.deepcopy(store.ideas[0])
    store.ideas = []
    store.run['mode'] = 'develop'
    store.run['state']['idea_input'] = {'idea_id': 'i1', 'seed': store.original_idea['seed'],
        'latest_note': note(), 'field_brief': store.run['state']['field_brief']}
    revised = note()
    revised.update(decision='drop', reason='近邻已经覆盖原始想法')
    revised['current_understanding'] = copy.deepcopy(store.original_idea['note']['current_understanding'])
    store.run['state']['prestudy_note'] = revised
    payload = build_polish_payload(store, 'r1')
    assert payload['candidates'][0]['decision'] == 'drop'
    assert payload['candidates'][0]['writing_brief']['decision_context'] == '近邻已经覆盖原始想法'
    store.run['state']['polish'] = written()
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    assert '本次放下' in paths['idea:i1'].read_text()
    assert store.original_idea['note']['decision'] == 'discuss'


def test_writer_and_json_correction_are_registered_no_tool_markdown():
    loader = PromptLoader(ASSETS)
    data = {'task_id': 'r1.polish', 'subject': {'run_id': 'r1'}, 'payload': {'original_question': '原始范围'}}
    prompt = loader.render('writer.POLISH', data, schema=StagePolish.model_json_schema())
    assert loader.manifest['prompts']['writer.POLISH']['tools'] == []
    assert {path for path in prompt.dependencies if path.startswith('common/')} == {'common/plain_research_writing.md'}
    assert not any(path.startswith('roles/') for path in prompt.dependencies)
    system = prompt.messages[0]['content']
    assert '必要术语首次出现时解释含义' in system
    assert '段落数量都没有最低配额' in system
    assert '选择能推进这一个问题的信息' in system
    assert '研究尚未验证时，预期按假设表述' in system
    assert '来源引用受候选source_ids、source_directory与citation_limit约束' in system
    repaired = render_repair(prompt, data, schema=StagePolish.model_json_schema(), previous_response={}, validation_errors=['missing'])
    assert '原始范围' in repaired.messages[1]['content'] and '不新增研究或事实' in repaired.messages[1]['content']
    assert '保留全文及研究判断' in repaired.messages[1]['content']
    assert repaired.messages[0] == prompt.messages[0]
    assert 'json' in repaired.messages[1]['content'].lower()


def test_compact_prestudy_preserves_current_limits_and_excludes_history_and_field_survey(tmp_path):
    store = prepared_store(tmp_path)
    payload = build_polish_payload(store, 'r1')
    payload['stage'] = 'develop'
    current = {'core_insight': '只能讨论群体关系，不能确定每个样本的原因。',
               'invalidated_premises': ['逐样本确定归因已撤回。'],
               'decisive_unknown': '校准是否可迁移仍不清楚。',
               'why_existing_insufficient': '现有结果没有回答迁移条件。'}
    # Rebuild from a current scientific note, before forming the writing view.
    store.ideas[0]['note']['current_understanding'] = current
    payload = build_polish_payload(store, 'r1')
    payload['stage'] = 'develop'
    payload['source_directory'].append({'source_id': 'field-only', 'title': '广泛背景', 'url': None, 'notes': []})
    original = copy.deepcopy(payload)
    compact = compact_polish_payload(payload)
    assert payload == original
    assert 'field_brief' not in compact
    assert len(compact['source_directory']) == 2
    actual = compact['candidates'][0]['writing_brief']
    assert actual['proposal']['hypothesis'] == current['core_insight']
    assert actual['decisive_unknown'] == current['decisive_unknown']
    assert current['invalidated_premises'][0] not in json.dumps(compact, ensure_ascii=False)
    assert compact['candidates'][0]['technical_context']['audit_reference']['idea_id'] == 'i1'
    assert actual == original['candidates'][0]['writing_brief']


def test_revision_render_changes_display_title_without_mutating_source_run_or_reports(tmp_path):
    store = prepared_store(tmp_path)
    store.run['state']['polish'] = written()
    old_paths = render_run(store, 'r1', tmp_path / 'original', PromptLoader(ASSETS))
    original_files = {key: path.read_bytes() for key, path in old_paths.items()}
    before = copy.deepcopy(store.__dict__)
    revision = written()
    revision['candidates'][0]['presentation_title'] = '信息何时影响决策'
    revision['candidates'][0]['text'] = '修订后的第一短段。\n\n关键未知仍未解决。'
    paths = render_run(store, 'r1', tmp_path / 'revision', PromptLoader(ASSETS),
                       polish_override=revision, polish_payload=build_polish_payload(store, 'r1'))
    detail = paths['idea:i1'].read_text()
    assert detail.startswith('# 信息何时影响决策')
    assert '时机改变信息作用' not in detail
    assert paths['technical_idea:i1'].read_text().startswith('# 时机改变信息作用')
    assert '[详细预研记录](i1.technical.md)' in detail
    assert '信息何时影响决策' in paths['overview'].read_text()
    assert revision['candidates'][0]['text'] in detail
    assert paths['technical_idea:i1'].read_bytes() == original_files['technical_idea:i1']
    assert all(path.read_bytes() == original_files[key] for key, path in old_paths.items())
    assert store.__dict__ == before


def test_old_writer_uses_frozen_source_directory_even_if_new_prestudy_payload_is_smaller(tmp_path):
    store = prepared_store(tmp_path)
    old_input = build_polish_payload(store, 'r1')
    old_input['source_directory'].append({'source_id': 'field-only', 'title': '原总览引用', 'url': None, 'notes': []})
    result = written()
    result['cited_source_ids'].append('field-only')
    store.run['state'].update(polish=result, task_inputs={'polish': {'payload': old_input}})
    paths = render_run(store, 'r1', tmp_path / 'legacy', PromptLoader(ASSETS))
    assert '原总览引用' in paths['overview'].read_text()
    assert paths['idea:i1'].read_text().startswith('# 时机改变信息作用')
    assert StagePolish.model_validate(result).candidates[0].presentation_title is None


def test_saved_writer_output_renders_with_its_frozen_bundle_not_new_disk_templates(tmp_path, monkeypatch):
    import shutil
    import arc.reports as reports
    store = prepared_store(tmp_path)
    # Historical accepted output has no presentation_title or new template fields.
    store.run['state']['polish'] = written()
    frozen = store.artifact_root / 'runs' / 'r1' / 'prompt-resources'
    current = tmp_path / 'current-assets'
    shutil.copytree(ASSETS, frozen)
    shutil.copytree(ASSETS, current)
    (frozen / 'discover/polished_idea.md').write_text('# 历史模板\n\n{{ text }}\n')
    (current / 'discover/polished_idea.md').write_text('# 新模板\n{{ unavailable_to_old_renderer }}\n')
    loader_type = PromptLoader
    monkeypatch.setattr(reports, 'PromptLoader', lambda root=None: loader_type(root or current))
    paths = render_run(store, 'r1', tmp_path / 'frozen-report')
    assert paths['idea:i1'].read_text().startswith('# 历史模板')
    assert written()['candidates'][0]['text'] in paths['idea:i1'].read_text()
    # Writer-only revisions deliberately pass their new bundle; the original run
    # snapshot must not override that explicit choice.
    (current / 'discover/polished_idea.md').write_text('# 独立成文版本\n\n{{ text }}\n')
    paths = render_run(store, 'r1', tmp_path / 'explicit-revision', loader_type(current),
                       polish_override=written(), polish_payload=build_polish_payload(store, 'r1'))
    assert paths['idea:i1'].read_text().startswith('# 独立成文版本')


def test_historical_run_without_resource_snapshot_still_renders(tmp_path):
    store = prepared_store(tmp_path)
    store.run['state']['polish'] = written()
    paths = render_run(store, 'r1', tmp_path / 'no-snapshot')
    assert written()['stage_summary'] in paths['overview'].read_text()


def test_workflow_publish_passes_its_runtime_loader(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from arc.discovery_workflow import publish
    loader = PromptLoader(ASSETS)
    engine = SimpleNamespace(store=object(), runtime=SimpleNamespace(loader=loader),
                             settings=SimpleNamespace(data_dir=tmp_path))
    seen = []
    monkeypatch.setattr('arc.reports.render_run', lambda *args: seen.append(args))
    publish(engine, 'r1')
    assert seen[0][3] is loader


@pytest.mark.parametrize('field,value', [
    ('stage_summary', '完整摘要。' * 300),
    ('overview', '完整背景与条件。' * 1600),
    ('candidate', '核心设想与必要条件。' * 2000),
    ('candidate', '单个自然段中的完整说明。' * 400),
])
def test_complete_long_writing_is_accepted_and_rendered_without_shortening(tmp_path, field, value):
    store = prepared_store(tmp_path)
    payload = build_polish_payload(store, 'r1')
    assert 'writing_limits' not in payload
    assert payload['citation_limit'] == MAX_CITED_SOURCES
    result = written()
    if field == 'candidate':
        result['candidates'][0]['text'] = value
    else:
        result[field] = value
    accepted = validate_polish(result, payload)
    assert (accepted.candidates[0].text if field == 'candidate' else getattr(accepted, field)) == value
    store.run['state']['polish'] = result
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    path = paths['idea:i1'] if field == 'candidate' else paths['overview']
    assert value in path.read_text(encoding='utf-8')
    # Older frozen inputs retain their bytes; their former size values have no effect.
    payload['writing_limits'] = {'stage_summary_max_chars': 1, 'overview_max_chars': 1,
                                'candidate_text_max_chars': 1, 'paragraph_max_chars': 1,
                                'max_cited_sources': MAX_CITED_SOURCES}
    assert validate_polish(result, payload).model_dump(mode='json') == accepted.model_dump(mode='json')


def test_risk_analysis_is_complete_in_technical_report_and_main_prose_is_preserved(tmp_path):
    store = prepared_store(tmp_path)
    result = written()
    risk = '风险影响核心命题，比较简单规则和内部信号的选择可以区分定义差异与决策用途。' * 100
    result['candidates'][0]['technical_analysis'] = risk
    store.run['state']['polish'] = result
    before = copy.deepcopy(store.__dict__)
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    assert result['candidates'][0]['text'] in paths['idea:i1'].read_text()
    assert risk not in paths['idea:i1'].read_text()
    assert risk in paths['technical_idea:i1'].read_text()
    assert note()['main_risk'] in paths['technical_idea:i1'].read_text()
    again = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    assert again['technical_idea:i1'].read_text().count(risk) == 1
    assert store.__dict__ == before


def test_writing_reference_limit_keeps_short_or_unreferenced_results_valid(tmp_path):
    payload = build_polish_payload(prepared_store(tmp_path), 'r1')
    result = written()
    extra = ['s3', 's4', 's5', 's6']
    payload['source_directory'].extend({'source_id': sid, 'title': sid, 'url': None, 'notes': []} for sid in extra)
    payload['candidates'][0]['source_ids'].extend(extra)
    result['candidates'][0]['cited_source_ids'].extend(extra)
    with pytest.raises(ValueError, match='6 references; maximum 5'):
        validate_polish(result, payload)
    result['candidates'][0]['cited_source_ids'] = []
    assert validate_polish(result, payload)


@pytest.mark.asyncio
async def test_complete_long_response_makes_one_request_and_preserves_raw_output(tmp_path):
    from .test_runtime import setup_runtime, answer, sse, SUBJECT
    payload = {'candidates': [], 'source_directory': [], 'citation_limit': MAX_CITED_SOURCES}
    long_result = {'stage_summary': '完整的阶段认识。' * 500, 'overview': '完整适用条件。' * 1000,
                   'candidates': [], 'cited_source_ids': []}
    response = answer()
    response['result'] = long_result
    runtime, store, ledger, requests = setup_runtime(tmp_path, [sse(json.dumps(response))])
    runtime.role_models['writer'] = 'deepseek-v4-flash'
    try:
        result = await runtime.invoke('writer', 'POLISH', payload, StagePolish, SUBJECT, 'task_fixture')
        assert result.result.model_dump(mode='json') == long_result
        assert len(requests) == 1
        task = store.get_task('task_fixture')
        state = json.loads(store.read_artifact(task.response_artifact_path))
        assert state.get('repair_counts', {}).get('output_json', 0) == 0
        assert task.accepted_result['result'] == long_result
        receipt = ledger.get_call(task.attempt_ids[0])['metadata']
        saved_response = json.loads(store.read_artifact(receipt['response_artifact_path']))
        assert json.loads(saved_response['response']['message']['content'])['result'] == long_result
    finally:
        await runtime.close()


def limited_entry():
    return {'reason': 'critical_source_unavailable', 'closure_key': 'idea1.check.close',
            'status': 'parked', 'unresolved_evidence_requests': [
                {'question': '关键近邻是否已经覆盖这个操作？', 'rationale': 'Full original request not needed by writer',
                 'source_ids': ['s2']}]}


def test_limited_check_writer_and_report_keep_missing_material_not_prior_recommendation(tmp_path):
    store = prepared_store(tmp_path)
    store.ideas[0]['status'] = 'evidence_limited'
    # Defensively refuse even a stale older note when the current status is limited.
    store.run['state']['evidence_limits'] = {'idea1.check': limited_entry()}
    before = copy.deepcopy(store.__dict__)
    payload = build_polish_payload(store, 'r1')
    candidate = payload['candidates'][0]
    assert candidate['decision'] == 'evidence_limited' and 'note' not in candidate
    assert candidate['evidence_limits'][0]['unresolved_questions'] == ['关键近邻是否已经覆盖这个操作？']
    assert 'closure_key' not in json.dumps(payload) and 'Full original request' not in json.dumps(payload)
    result = written()
    result['candidates'][0]['cited_source_ids'] = ['s1']
    result['cited_source_ids'] = ['s1']
    result['stage_summary'] = '文献核查受限，当前保留原问题及待查事项。'
    result['candidates'][0]['text'] = '已尝试核查关键近邻，但相关材料仍无法取得。原始思路保留待查，不构成推荐。'
    paths = render_run(store, 'r1', tmp_path / 'limited', PromptLoader(ASSETS),
                       polish_override=result, polish_payload=payload)
    technical = paths['technical_idea:i1'].read_text()
    assert '文献受限，保留待查' in paths['overview'].read_text() + technical
    assert '已尝试核查' in technical and '关键近邻是否已经覆盖这个操作' in technical
    assert '当前没有可接受的预研结论' in technical
    assert '未做定向预研' not in technical and '值得讨论' not in paths['idea:i1'].read_text()
    assert paths['idea:i1'].read_text().splitlines()[2] == '文献受限，保留待查。'
    assert '已尝试核查关键近邻，但相关材料仍无法取得' in paths['idea:i1'].read_text()
    assert '0 个值得讨论' in paths['technical_overview'].read_text()
    assert store.__dict__ == before


@pytest.mark.parametrize('mode', ['develop', 'run'])
def test_failed_limited_prestudy_does_not_display_inherited_discovery_note(tmp_path, mode):
    store = prepared_store(tmp_path)
    store.original_idea = copy.deepcopy(store.ideas[0])
    store.ideas = []
    store.run['mode'] = mode
    store.run['state'].update(idea_input={'idea_id': 'i1', 'seed': store.original_idea['seed'],
                             'latest_note': note(), 'field_brief': store.run['state']['field_brief']},
                             prestudy_evidence_limited=True,
                             evidence_limits={'prestudy': limited_entry()})
    payload = build_polish_payload(store, 'r1')
    assert payload['candidates'][0]['decision'] == 'evidence_limited'
    assert 'note' not in payload['candidates'][0]
    assert payload['candidates'][0]['evidence_limits']
    paths = render_run(store, 'r1', tmp_path / mode, PromptLoader(ASSETS))
    assert '文献受限，保留待查' in paths['idea:i1'].read_text()
    assert '未做定向预研' not in paths['idea:i1'].read_text()
    assert '0 个值得讨论' in paths['overview'].read_text()
    assert store.original_idea['note']['decision'] == 'discuss'


def test_failed_survey_without_conclusions_is_explicit_and_does_not_invent_research(tmp_path):
    store = prepared_store(tmp_path)
    store.ideas = []
    store.run['state']['field_brief'] = {'overview': '', 'research_lines': [], 'openings': [],
        'source_notes': [], 'search_limits': ['未取得关键文献，领域结论暂缺。']}
    store.run['state']['evidence_limits'] = {'survey': limited_entry()}
    paths = render_run(store, 'r1', tmp_path / 'survey', PromptLoader(ASSETS))
    assert '尚未形成可接受结论' in paths['field_brief'].read_text()
    assert '未取得关键文献' in paths['field_brief'].read_text()
    payload = build_polish_payload(store, 'r1')
    assert 'field_brief' not in payload and payload['candidates'] == []
    assert payload['evidence_limits'][0]['task'] == 'survey'


def test_accepted_limited_closure_keeps_its_actual_lead_and_unresolved_questions(tmp_path):
    store = prepared_store(tmp_path)
    store.ideas[0]['note']['decision'] = 'lead'
    store.run['state']['evidence_limits'] = {'idea1.check': dict(limited_entry(), status='limited')}
    payload = build_polish_payload(store, 'r1')
    assert payload['candidates'][0]['decision'] == 'lead'
    assert payload['candidates'][0]['technical_context']['limits'] == note()['limits']
    assert payload['candidates'][0]['evidence_limits'][0]['unresolved_questions']


def test_writer_repair_repeats_current_subject_not_historical_payload_identity():
    current = {'run_id': 'writing-revision.original-run', 'campaign_id': None,
               'card_id': None, 'card_version': None}
    data = {'task_id': 'writing-revision.original-run.polish', 'subject': current,
            'payload': {'run_id': 'original-run'}}
    prompt = PromptLoader(ASSETS).render('writer.POLISH', data, schema=StagePolish.model_json_schema(),
        repair={'previous_response': {'subject': {'run_id': 'original-run'}},
                'validation_errors': ['SUBJECT_OR_TASK_MISMATCH']})
    instruction = prompt.messages[1]['content']
    identity_section = instruction.split('本次任务对象', 1)[1].split('原始材料', 1)[0]
    assert 'writing-revision.original-run' in identity_section
    assert 'campaign_id' in identity_section and 'card_version' in identity_section
    assert '材料中的历史运行编号不是本次任务身份' in identity_section
