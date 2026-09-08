"""Fixture integrity tests, not a claim about model correction performance."""
from collections import Counter
import json
from pathlib import Path
from arc.schemas import CardDraft
from arc.store import Store
from tests.helpers.scientific_cases import load_scientific_cases,model_payload,register_scientific_case

def test_eight_paired_cases_are_schema_valid_and_expected_is_private():
    cases=load_scientific_cases()
    assert len(cases)==8
    assert Counter(case['pair_id'] for case in cases)=={'scope':2,'attribution':2,'interaction':2,'partition':2}
    for case in cases:
        payload=model_payload(case)
        CardDraft.model_validate(payload['card'])
        serialized=json.dumps(payload,ensure_ascii=False)
        assert 'expected' not in payload and 'case_id' not in payload and 'pair_id' not in payload
        assert 'repair_acceptance' not in serialized and 'has_target_hard_error' not in serialized
        assert case['case_id'] not in serialized
        for evidence in payload['evidence']:
            source=next(source for source in payload['sources'] if source['source_id']==evidence['source_id'])
            assert evidence['excerpt'] in source['content']

def test_pairs_keep_original_question_and_evidence_fixed():
    cases=load_scientific_cases()
    for pair_id in {case['pair_id'] for case in cases}:
        pair=[case for case in cases if case['pair_id']==pair_id]
        assert sum(case['expected']['has_target_hard_error'] for case in pair)==1
        good,bad=[model_payload(case) for case in pair]
        assert good['original_task']==bad['original_task']
        assert good['sources']==bad['sources'] and good['evidence']==bad['evidence']
        assert good['card']!=bad['card']


def _differences(left, right, path=''):
    if isinstance(left, dict) and isinstance(right, dict):
        assert left.keys() == right.keys()
        return set().union(*(_differences(left[key], right[key], f'{path}/{key}') for key in left))
    if isinstance(left, list) and isinstance(right, list):
        assert len(left) == len(right)
        return set().union(*(_differences(a, b, f'{path}/{index}') for index, (a, b) in enumerate(zip(left, right))))
    return {path} if left != right else set()


def test_each_pair_changes_only_the_intended_error_locations():
    allowed = {
        'scope': {'/card/method/simplest_path', '/card/minimal_test/intervention', '/card/minimal_test/measurements/0'},
        'attribution': {'/card/motivation/observation_or_deficit', '/card/claims/0/text'},
        'interaction': {'/card/method/simplest_path', '/card/minimal_test/intervention'},
        'partition': {'/card/minimal_test/measurements/0'},
    }
    cases = load_scientific_cases()
    for pair_id, expected_paths in allowed.items():
        good, bad = [model_payload(case) for case in cases if case['pair_id'] == pair_id]
        assert _differences(good, bad) == expected_paths


def test_replication_controls_do_not_call_the_published_effect_unmeasured():
    for case in load_scientific_cases():
        payload = model_payload(case)
        card = payload['card']
        assert card['closest_work_delta']['remaining_claim'] != '候选中的拟检验量尚未测得。'
        if case['pair_id'] != 'attribution':
            continue
        assert '本地复现' in payload['original_task']['topic']
        assert '已经测量' in card['closest_work_delta']['established_claim']
        assert '原报告中的效应已经测得' in card['closest_work_delta']['remaining_claim']
        assert '不构成新的科学贡献' in card['contribution']['decision_changed']
        assert '逐方法' in card['minimal_test']['measurements'][0]
        assert '无需重新训练' in payload['sources'][0]['content']
        assert '未压缩基线 | 62；压缩表示 | 71' in payload['sources'][0]['content']


def test_v1_is_preserved_as_development_history_not_relabelled():
    fixtures = Path(__file__).parent / 'fixtures'
    old = json.loads((fixtures / 'scientific_error_pairs_v1.json').read_text(encoding='utf-8'))
    current = json.loads((fixtures / 'scientific_error_pairs.json').read_text(encoding='utf-8'))
    assert 'fixture_version' not in old and current['fixture_version'] == 2
    old_case = next(case for case in old['cases'] if case['case_id'] == 'attribution_correct')
    assert old_case['model_visible']['original_task']['topic'] == '压缩表示能否提高同一任务的低预算准确率？'
    assert old_case['model_visible']['card']['closest_work_delta']['remaining_claim'] == '候选中的拟检验量尚未测得。'
    assert old_case['expected']['not_a_quality_label'] is True

def test_explicit_registration_does_not_create_runs_or_tasks(tmp_path):
    for case in load_scientific_cases():
        store=Store(tmp_path/(case['case_id']+'.sqlite'))
        card,payload=register_scientific_case(store,case,creation_key=case['case_id'])
        assert card.draft.model_dump(mode='json')==payload['card']
        assert store.get_record(payload['sources'][0]['source_id'])['access_status']=='retrieved'
        assert store.get_record(payload['evidence'][0]['evidence_id'])['verification_status']=='verified'
        with store._connect() as db:
            assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]==0
            assert db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]==0
