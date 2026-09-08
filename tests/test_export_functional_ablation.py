"""A–E export keeps attribution, account independence and uncertainty explicit."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('ablation_export', Path(__file__).parents[1] / 'scripts/export_functional_ablation.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def cost(account, amount):
    return dict(account_id=account, parent_id='historical-parent', spent_lower_cny=str(amount),
                spent_upper_cny=str(amount), reserved_cny='0', unsettled_lower_cny='0', unknown_calls=0)


def files(tmp_path, report=None):
    root = tmp_path / 'artifacts/functional-evaluations/example'
    root.mkdir(parents=True)
    manifest = dict(experiment_id='example', seed=4, source_run_id='material-only',
                    conditions={key: 'Condition ' + key for key in 'ABCDE'},
                    material=dict(original_task={'topic': 'The original question', 'boundaries': ['No training']},
                                  sources=[{'content': 'FULL_SOURCE_MUST_NOT_BE_EXPORTED'}], evidence=[{}]))
    (root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    if report is not None:
        (root / 'report.json').write_text(json.dumps(report), encoding='utf-8')
    return root


def test_independent_costs_reuse_and_actual_changes_do_not_become_quality_claims(tmp_path):
    draft = dict(title='A question', problem_anchor={'question': 'The original question'},
                 contribution={'knowledge_increment': 'Separate two explanations'},
                 minimal_test={'measurements': ['Three wrong categories']}, risks={'decisive_risks': ['Confounding']})
    arms = {key: dict(draft=deepcopy(draft), judgment={'selection': 'MAIN_REPORT', 'why_worth_investigating': 'Reason'},
                     status='COMPLETED', run_id='example.' + key, cost=cost('example.' + key, number))
            for number, key in enumerate('ABCDE', 1)}
    arms['D'].update(judgment={'action': 'revise', 'decisive_findings': [{'reason': 'Missing success'}]})
    arms['E']['draft']['minimal_test']['measurements'] = ['Four exhaustive categories']
    arms['E'].update(candidate_origin='example.A', initial_review_origin='example.D.science.review',
                     judgment={'action': 'reject', 'value_reason': 'Correct but routine'})
    report = dict(status='completed', conditions=arms, judge_status='COMPLETED', judge_cost=cost('example.judge', 2),
                  parent_cost=cost('historical-parent', 999), evaluations=[])
    files(tmp_path, report)
    summary = exporter.export_ablation(tmp_path, 'example')
    assert summary['experiment_cost']['known_subtotal']['spent_upper_cny'] == '17.000000'
    assert 'historical-parent' not in summary['experiment_cost']['included_account_ids']
    assert summary['reuse']['A_D_drafts_equal'] is True
    assert summary['reuse']['E_initial_review_recorded_as_D'] is True
    assert summary['E_changes_from_A'] == [{'location': '/minimal_test/measurements/0',
                                          'before': 'Three wrong categories', 'after': 'Four exhaustive categories'}]
    assert summary['quality_improved'] is None
    assert summary['human_judgment']['research_value_improved'] is None
    assert 'FULL_SOURCE_MUST_NOT_BE_EXPORTED' not in json.dumps(summary)


def test_each_anonymous_order_uses_its_own_identity_map(tmp_path):
    value = dict(per_candidate_findings=[{'candidate_id': 'candidate_1', 'findings': ['Stronger'], 'evidence_ids': []}],
                 preference_if_requested='candidate_1 is preferred; candidate_2 has a defect.', uncertainty='Limited')
    forward = dict(order='forward', identity_map_private={'candidate_1': {'system': 'A'}, 'candidate_2': {'system': 'E'}}, evaluation=value)
    swapped = dict(order='swapped', identity_map_private={'candidate_1': {'system': 'E'}, 'candidate_2': {'system': 'A'}}, evaluation=value)
    files(tmp_path, {'evaluations': [forward, swapped]})
    summary = exporter.export_ablation(tmp_path, 'example')
    first, second = summary['evaluations']
    assert first['candidate_findings'][0]['system'] == 'A'
    assert second['candidate_findings'][0]['system'] == 'E'
    assert first['preference_with_system_labels'].startswith('A [candidate_1]')
    assert second['preference_with_system_labels'].startswith('E [candidate_1]')
    assert first['preference_original'] == second['preference_original']


def test_partial_failure_and_absent_candidate_are_not_reported_as_finished_or_free(tmp_path):
    files(tmp_path, {'status': 'incomplete', 'conditions': {
        'A': {'draft': None, 'status': 'COMPLETED', 'not_run_reason': 'STOP', 'cost': cost('example.A', 1)},
        'B': {'draft': None, 'status': 'PAUSED_PROTOCOL', 'stop_reason': 'MALFORMED_OUTPUT'}}})
    summary = exporter.export_ablation(tmp_path, 'example')
    assert summary['conditions']['A']['candidate_present'] is False
    assert summary['conditions']['B']['status'] == 'PAUSED_PROTOCOL'
    assert summary['conditions']['C']['status'] == 'NOT_RECORDED'
    assert summary['E_changes_from_A'] is None
    assert summary['experiment_cost']['all_stage_costs_recorded'] is False
    assert set(summary['experiment_cost']['missing_stage_costs']) == {'B', 'C', 'D', 'E', 'judge'}
    assert summary['experiment_cost']['known_subtotal']['spent_upper_cny'] == '1.000000'
    markdown = exporter.render_markdown(summary)
    assert 'MALFORMED_OUTPUT' in markdown and '尚无可展示候选' in markdown
    assert '人工判断（待填写）' in markdown


def test_manifest_only_is_a_prepared_experiment_not_a_generation_result(tmp_path):
    files(tmp_path)
    summary = exporter.export_ablation(tmp_path, 'example')
    assert summary['status'] == 'NOT_RECORDED'
    assert all(not item['candidate_present'] for item in summary['conditions'].values())
    assert summary['quality_improved'] is None
