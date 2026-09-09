from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from arc.prompting import PromptLoader, render_repair
from arc.reports import render_run

ASSETS = Path(__file__).resolve().parents[1] / 'prompts'


def seed():
    return {'title': '时机改变信息作用', 'question': '原始问题', 'insight': '信息已有但抵达决策太晚',
            'why_it_matters': '减少真实任务中无效补充信息', 'difference_from_known': '检查进入决策时机而非仅增加信息',
            'source_ids': ['s1'], 'key_unknown': '时间关系还只是假设'}


def note():
    return {'seed': seed(), 'decision': 'discuss', 'reason': '有值得讨论的具体差异',
            'nearest_work': [{'source_id': 's2', 'already_established': '已研究信息覆盖',
                              'remaining_difference': '尚待查时机的作用', 'uncertainty': '近邻只读摘要'}],
            'feasibility': '已有接口可读取时序信息，尚未执行实验',
            'resources': {'gpu_type': None, 'gpu_count': None, 'training_hours_estimate': None,
                          'inference_hours_estimate': None, 'basis': '缺少工作量依据，暂不估时'},
            'main_risk': '时机可能只是任务难度的代理', 'next_question': '材料是否存在可比的决策时点？',
            'source_notes': [{'source_id': 's2', 'finding': '原作者只报告覆盖结果', 'relevance': '核心近邻',
                              'access': 'abstract', 'limits': '全文未取得'}],
            'limits': ['尚未检验因果关系'], 'changes_from_seed': ['去掉没有依据的效果承诺']}


class Store:
    def __init__(self, tmp_path):
        self.db_path = tmp_path / 'state.sqlite'
        self.artifact_root = tmp_path / 'artifacts'
        self.run = {'run_id': 'r1', 'mode': 'discover', 'status': 'PAUSED_BUDGET',
                    'stop_reason': 'next_request_not_admitted', 'budget_account_id': None,
                    'state': {'discover_first': True, 'source_ids': ['s1', 's2', 'noise'],
                              'first_seed_at': '2026-09-09T01:00:00Z',
                              'field_brief': {'overview': '研究路线有不同信息利用时点', 'research_lines': ['从信息量到使用条件'],
                                              'openings': ['补充信息何时必要'], 'search_limits': ['只读到关键摘要'],
                                              'source_notes': [{'source_id': 's1', 'finding': '存在信息未被利用的结果',
                                                               'relevance': '启发关系', 'access': 'passage', 'limits': '未读其他部分'}]}}}
        self.ideas = [{'idea_id': 'i1', 'run_id': 'r1', 'draw_id': 1, 'topic': '原始问题', 'brief_version': 1,
                       'seed': seed(), 'triage': {'action': 'investigate', 'reason': '需要补近邻',
                                                  'strongest_objection': '时机有混淆', 'check_questions': ['覆盖是不是已被解决？']},
                       'note': None, 'status': 'pending'}]
    def get_run(self, run_id): return self.run
    def list_discovery_ideas(self, *, run_id): return self.ideas
    def get_discovery_idea(self, idea_id): return self.original_idea
    def list_tasks(self, run_id): return []
    def list_capability_requests(self, run_id): return []
    def list_sources(self, ids=None):
        return [{'source_id': key, 'title': title, 'url': 'https://example.org/' + key}
                for key, title in [('s1', '启发文献'), ('s2', '最近工作'), ('noise', '无关检索命中')]
                if ids is None or key in ids]
    def list_cards(self, **kwargs): raise AssertionError('light discovery must not construct or read CardDraft')


def test_pending_survives_budget_pause_without_becoming_recommendation(tmp_path):
    store = Store(tmp_path)
    before = copy.deepcopy(store.__dict__)
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    assert store.__dict__ == before
    text = paths['overview'].read_text()
    detail = paths['idea:i1'].read_text()
    assert '0 个值得讨论' in text and '1 个待预研' in text
    assert 'PAUSED_BUDGET' in text and 'arc resume r1' in text
    assert '不是已推荐结果' in detail and '覆盖是不是已被解决' in detail
    assert '无关检索命中' not in text + detail
    assert '无关检索命中' in paths['search_sources'].read_text()
    usage = json.loads(paths['usage'].read_text())
    assert usage['first_seed_at'] == '2026-09-09T01:00:00Z' and usage['first_note_at'] is None


def test_note_direct_render_has_only_relevant_refs_and_keeps_unknowns(tmp_path):
    store = Store(tmp_path)
    store.ideas[0].update(note=note(), status='checked')
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    text = paths['idea:i1'].read_text()
    assert '值得讨论' in text and '不是已推荐结果' not in text
    assert 'https://example.org/s1' in text and 'https://example.org/s2' in text
    assert '摘要；全文未取得' in text and '去掉没有依据的效果承诺' in text
    assert '缺少工作量依据' in text and 'GPU：未记录' in text
    assert '无关检索命中' not in text
    assert text.index('本次实质调整') < text.index('初始灵感（预研前') < text.index('文献已经做到哪里')
    overview = paths['overview'].read_text()
    assert overview.index('有值得讨论的具体差异') < overview.index('共享调研概览')
    assert note()['seed']['insight'] not in overview


@pytest.mark.parametrize('status,label', [('drop', '本次没有继续的方向'), ('park', '还值得留意的线索')])
def test_early_editor_decisions_are_not_checked_notes(tmp_path, status, label):
    store = Store(tmp_path)
    store.ideas[0].update(status=status)
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    assert label in paths['overview'].read_text()
    assert '未做定向预研' in paths['idea:i1'].read_text()


def test_non_submission_never_fabricates_idea(tmp_path):
    store = Store(tmp_path)
    store.ideas = [{**store.ideas[0], 'seed': None, 'status': 'skip', 'reason': '暂未找到不同认识'}]
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    assert '已保存 0 个想法' in paths['overview'].read_text()
    assert '暂未找到不同认识' in paths['overview'].read_text()
    assert 'idea:i1' not in paths


@pytest.mark.parametrize('prompt_id', ['scout.SURVEY', 'scout.CHECK', 'ideator.SKETCH', 'editor.TRIAGE', 'scout.DEVELOP', 'scout.PRESSURE'])
def test_light_prompts_and_saved_json_correction_remain_markdown_only(prompt_id):
    loader = PromptLoader(ASSETS)
    data = {'task_id': 'r1.task', 'subject': {'run_id': 'r1'}, 'payload': {'original_task': '真实原题'}}
    schema = {'type': 'object', 'properties': {'result': {'type': 'object'}}}
    prompt = loader.render(prompt_id, data, schema=schema)
    assert not any(name.startswith('common/') or name.startswith('roles/') for name in prompt.dependencies)
    assert '真实原题' in prompt.messages[1]['content']
    assert not any(model.lower() in prompt.messages[0]['content'].lower() for model in ['deepseek', 'flash', 'claude', 'v4-pro'])
    repair = render_repair(prompt, data, schema=schema, previous_response={}, validation_errors=['missing'])
    assert '真实原题' in repair.messages[1]['content']
    assert '不能为了通过校验增加实验' in repair.messages[1]['content']
    if prompt_id in {'ideator.SKETCH', 'editor.TRIAGE'}:
        assert loader.manifest['prompts'][prompt_id]['tools'] == []
    if prompt_id.startswith('scout.') and prompt_id not in {'scout.CHECK', 'scout.SURVEY'}:
        assert 'discover/researcher.md' not in prompt.dependencies


def test_selected_idea_stage_uses_its_own_result_and_keeps_inherited_input(tmp_path):
    store = Store(tmp_path)
    store.original_idea = {**store.ideas[0], 'note': note(), 'status': 'checked'}
    store.ideas = []
    store.run['mode'] = 'develop'
    store.run['state']['idea_input'] = {'idea_id': 'i1', 'seed': seed(), 'latest_note': note(),
                                      'field_brief': store.run['state'].pop('field_brief')}
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    assert '1 个待预研' in paths['overview'].read_text()
    assert '值得讨论' not in paths['idea:i1'].read_text()
    assert '研究路线有不同信息利用时点' in paths['field_brief'].read_text()
    assert json.loads(paths['input_idea'].read_text())['latest_note']['decision'] == 'discuss'
    updated = note()
    updated.update(decision='drop', reason='新近邻已经覆盖核心操作')
    store.run['state']['prestudy_note'] = updated
    paths = render_run(store, 'r1', tmp_path / 'report', PromptLoader(ASSETS))
    assert '已选想法的预研展开' in paths['overview'].read_text()
    assert '新近邻已经覆盖核心操作' in paths['idea:i1'].read_text()
    assert '本次放下' in paths['idea:i1'].read_text()
    assert store.original_idea['note']['decision'] == 'discuss'


def test_usage_distinguishes_model_requests_tools_and_unsent_reservations(tmp_path):
    from arc.reports import _discovery_usage
    store = Store(tmp_path)
    calls = [{'state': 'SETTLED', 'tool_call_id': None, 'input_tokens': 100, 'completion_tokens': 20},
             {'state': 'SETTLED', 'tool_call_id': 'tool1', 'input_tokens': None},
             {'state': 'NOT_SENT', 'input_tokens': 999}, {'state': 'RESERVED'}]
    counts = _discovery_usage(store, [], calls)
    assert counts['model_requests'] == 1 and counts['input_tokens'] == 100
    assert counts['completion_tokens'] == 20 and counts['input_tokens_missing_requests'] == 0


def test_repair_prompt_explicitly_requests_json_without_diagnostic_keyword():
    loader = PromptLoader(ASSETS)
    data = {'task_id': 'check-json-repair', 'subject': {'campaign_id': None, 'run_id': 'r1',
            'card_id': None, 'card_version': None}, 'payload': {}}
    snapshot = loader.render('scout.CHECK', data, schema={'type': 'object'}, tool_profile=[])
    repair = loader.render_repair(snapshot, data, schema={'type': 'object'},
        previous_response={}, validation_errors=[{'type': 'extra_forbidden'}])
    assert 'json' in repair.messages[-1]['content'].lower()
