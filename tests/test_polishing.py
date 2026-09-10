from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from arc.polishing import StagePolish, build_polish_payload, validate_polish
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
    assert '400–700' in prompt.messages[0]['content'] and '600–1000' in prompt.messages[0]['content']
    repaired = render_repair(prompt, data, schema=StagePolish.model_json_schema(), previous_response={}, validation_errors=['missing'])
    assert '原始范围' in repaired.messages[1]['content'] and '不开展检索或科学复审' in repaired.messages[1]['content']
    assert 'json' in repaired.messages[1]['content'].lower()
