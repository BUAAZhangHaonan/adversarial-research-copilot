from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from arc.polishing import StagePolish, build_polish_payload, compact_polish_payload, validate_polish
from arc.prompting import PromptLoader, render_repair
from arc.reports import render_run
from .test_discovery_reports import Store, note, ASSETS


def prepared_store(tmp_path):
    store = Store(tmp_path)
    store.run.update(status='COMPLETED', stop_reason='human_selection')
    store.ideas[0].update(note=note(), status='checked')
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
    assert 'source_notes' not in payload['field_brief']
    assert 'source_notes' not in payload['candidates'][0]['note']
    assert payload['candidates'][0]['note']['limits'] == note()['limits']
    assert payload['candidates'][0]['decision'] == 'discuss'
    assert 'seed' not in payload['candidates'][0]  # Present once inside the complete technical note.
    assert 'noise' not in json.dumps(payload)


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
    payload['candidates'][0]['note']['feasibility'] = '原稿假设阈值0.95，仍需人检查。'
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
    assert '本次实质调整' in paths['technical_idea:i1'].read_text()
    assert 'ideas/i1.technical.md' in technical
    assert '查看原始技术报告' in report and 'i1.technical.md' in detail
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
    assert '本次实质调整' in paths['technical_idea:i1'].read_text()
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
    store.run['state']['prestudy_note'] = revised
    payload = build_polish_payload(store, 'r1')
    assert payload['candidates'][0]['decision'] == 'drop'
    assert payload['candidates'][0]['note']['reason'] == '近邻已经覆盖原始想法'
    store.run['state']['polish'] = written()
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    assert '本次放下' in paths['idea:i1'].read_text()
    assert store.original_idea['note']['decision'] == 'discuss'


def test_writer_and_json_correction_are_registered_no_tool_markdown():
    loader = PromptLoader(ASSETS)
    data = {'task_id': 'r1.polish', 'subject': {'run_id': 'r1'}, 'payload': {'original_question': '原始范围'}}
    prompt = loader.render('writer.POLISH', data, schema=StagePolish.model_json_schema())
    assert loader.manifest['prompts']['writer.POLISH']['tools'] == []
    assert not any(path.startswith('common/') or path.startswith('roles/') for path in prompt.dependencies)
    assert '首次出现时给出简短中文解释' in prompt.messages[0]['content']
    assert '200–350' in prompt.messages[0]['content'] and '500–800' in prompt.messages[0]['content']
    assert '80–160' in prompt.messages[0]['content'] and '3–5篇' in prompt.messages[0]['content']
    repaired = render_repair(prompt, data, schema=StagePolish.model_json_schema(), previous_response={}, validation_errors=['missing'])
    assert '原始范围' in repaired.messages[1]['content'] and '不开展检索或科学复审' in repaired.messages[1]['content']
    assert 'json' in repaired.messages[1]['content'].lower()


def test_compact_prestudy_preserves_current_limits_and_excludes_history_and_field_survey(tmp_path):
    store = prepared_store(tmp_path)
    payload = build_polish_payload(store, 'r1')
    payload['stage'] = 'develop'
    current = {'core_insight': '只能讨论群体关系，不能确定每个样本的原因。',
               'invalidated_premises': ['逐样本确定归因已撤回。'],
               'decisive_unknown': '校准是否可迁移仍不清楚。',
               'why_existing_insufficient': '现有结果没有回答迁移条件。'}
    payload['candidates'][0]['note']['current_understanding'] = current
    payload['source_directory'].append({'source_id': 'field-only', 'title': '广泛背景', 'url': None, 'notes': []})
    original = copy.deepcopy(payload)
    compact = compact_polish_payload(payload)
    assert payload == original
    assert 'field_brief' not in compact
    assert len(compact['source_directory']) == 2
    actual = compact['candidates'][0]['note']
    assert 'seed' not in actual and 'changes_from_seed' not in actual
    assert actual['current_understanding'] == current
    for key in ('reason', 'feasibility', 'main_risk', 'limits', 'resources', 'nearest_work'):
        assert actual[key] == original['candidates'][0]['note'][key]


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
    assert '原研究标题（历史）：时机改变信息作用' in detail
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
