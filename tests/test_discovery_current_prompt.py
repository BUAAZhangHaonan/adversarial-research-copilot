"""Check the installed task contracts expose the current-view handoff."""
from pathlib import Path

import pytest

from arc.discovery_models import CandidateCheck, TriageResult
from arc.prompting import PromptLoader

ROOT = Path(__file__).resolve().parents[1]


def task_data():
    return {'task_id': 'prompt-current-view', 'subject': {'run_id': 'current-run'},
            'payload': {'previous_directions': [{'draw_id': 'current-run.idea1',
                'latest_decision': 'lead', 'current_understanding': {
                    'core_insight': '仅剩一个待核查的机制区别',
                    'invalidated_premises': ['已撤回的背景前提'],
                    'decisive_unknown': '现有方法能否直接使用该信息',
                    'why_existing_insufficient': '尚不能确定已有方法不足'}}]}}


@pytest.mark.parametrize('task', ['scout.CHECK', 'scout.DEVELOP', 'scout.PRESSURE'])
def test_current_understanding_and_partial_field_revision_reach_effective_task(task):
    prompt = PromptLoader(ROOT / 'prompts').render(task, task_data(), schema=CandidateCheck.model_json_schema())
    system = prompt.messages[0]['content']
    user = prompt.messages[1]['content']
    assert 'current_understanding' in system and 'field_revision' in system
    assert '已撤回的背景前提' in user
    assert 'why_existing_insufficient' in user and 'invalidated_premises' in user
    assert user.count('"$defs"') == 1  # No duplicate complete schema/example payload.
    assert not any(path.startswith('common/') or path.startswith('roles/') for path in prompt.dependencies)
    parsed = CandidateCheck.model_json_schema()
    assert 'field_revision' not in parsed.get('required', [])
    assert 'current_understanding' not in parsed['$defs']['IdeaNote'].get('required', [])


def test_triage_sees_current_views_and_explicit_relations_without_a_fixed_winner():
    loader = PromptLoader(ROOT / 'prompts')
    prompt = loader.render('editor.TRIAGE', task_data(), schema=TriageResult.model_json_schema())
    system = prompt.messages[0]['content']
    user = prompt.messages[1]['content']
    assert all(name in system for name in ['previous_directions', 'previous_ideas', 'latest_decision', 'candidate_relation'])
    assert 'current-run.idea1' in user and '已撤回的背景前提' in user
    assert all(kind in user for kind in ['independent', 'alternative_route', 'evaluation_support', 'overlap', 'not_compared'])
    assert loader.manifest['prompts']['editor.TRIAGE']['tools'] == []
    assert 'discover/calibration.md' in prompt.dependencies
