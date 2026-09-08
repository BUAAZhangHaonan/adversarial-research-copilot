"""Export facts without turning textual repair or model rulings into acceptance."""
import importlib.util
import json
from pathlib import Path
import sqlite3

from arc.budget import BudgetLedger


spec = importlib.util.spec_from_file_location('export_controls', Path(__file__).parents[1] / 'scripts/export_functional_controls.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def setup_run(tmp_path, *, status='PAUSED_PROTOCOL', new_version=False):
    path = tmp_path / 'arc.sqlite'
    db = sqlite3.connect(path)
    db.executescript('''CREATE TABLE runs(id TEXT PRIMARY KEY,data TEXT);
        CREATE TABLE cards(card_id TEXT,version INTEGER,data TEXT);
        CREATE TABLE tasks(id TEXT,run_id TEXT,data TEXT);''')
    original = {'problem_anchor': {'question': 'A fixed question'}, 'minimal_test': {'measurements': ['wrong formula']}}
    final = json.loads(json.dumps(original))
    if new_version:
        final['minimal_test']['measurements'] = ['correct formula']
    finding = dict(finding_id='F1', location='/minimal_test/measurements/0', reason='Success category is missing.',
                   quoted_text='wrong formula', severity='repairable', required_change='Add success.', acceptance_test='Exhaustive categories.')
    initial = dict(action='revise', decisive_findings=[finding], verification_work=[{'answer': 'A counterexample exists.'}],
                   prior_findings=[], remaining_uncertainty=[])
    recheck = dict(action='reject', value_judgment='routine', decisive_findings=[],
                   prior_findings=[dict(finding_id='F1', status='resolved', reason='The proposed formula adds success.')])
    state = {'task_inputs': {'science.review': {'payload': {'review_target': original, 'card': {'version': 1}}}},
             'science.review': initial, 'science.recheck': recheck}
    if new_version:
        state.update(final_scientific_review=recheck, final_scientific_card_version=2)
    run = dict(run_id='example.case1', status=status, stop_reason='FIELD_STRUCTURE_INVALID' if status != 'COMPLETED' else None,
               card_id='card', card_version=2 if new_version else 1, state=state, budget_account_id='example.case1')
    db.execute('INSERT INTO runs VALUES (?,?)', (run['run_id'], json.dumps(run)))
    db.execute('INSERT INTO cards VALUES (?,?,?)', ('card', 1, json.dumps(dict(card_id='card', version=1, draft=original))))
    if new_version:
        db.execute('INSERT INTO cards VALUES (?,?,?)', ('card', 2, json.dumps(dict(card_id='card', version=2, draft=final))))
    # A malformed revision has no accepted result: do not recover a fake patch
    # from model prose or from the review's claimed resolution.
    task = dict(task_id='example.case1.science.revision', status='PAUSED_PROTOCOL', error='section_updates[0].value must be an object',
                response_artifact_path='responses/failed.json', accepted_result=None, reasoning='DO_NOT_EXPORT_REASONING')
    db.execute('INSERT INTO tasks VALUES (?,?,?)', (task['task_id'], run['run_id'], json.dumps(task)))
    db.commit()
    db.close()
    ledger = BudgetLedger(path)
    ledger.create_account(run['run_id'], '20')
    ledger.reserve(run['run_id'], 'unsettled-call', '1')
    cases = [dict(case_id=f'control_{i}', pair_id='pair', model_visible={'card': original},
                  expected=dict(target_locations=['minimal_test.measurements'], has_target_hard_error=True)) for i in range(2)]
    fixture = tmp_path / 'scientific_error_pairs.json'
    fixture.write_text(json.dumps(dict(fixture_version=2, cases=cases)), encoding='utf-8')
    return fixture


def test_paused_export_retains_failure_and_does_not_claim_proposed_repair_was_saved(tmp_path, monkeypatch):
    fixture = setup_run(tmp_path)
    connect = sqlite3.connect
    opened = []
    def readonly_connect(path, **kwargs):
        opened.append((path, kwargs))
        assert str(path).endswith('?mode=ro') and kwargs['uri'] is True
        return connect(path, **kwargs)
    monkeypatch.setattr(exporter.sqlite3, 'connect', readonly_connect)
    report = exporter.export_controls(tmp_path, 'example', fixture)
    assert opened
    assert report['present_case_count'] == 1 and report['missing_case_ids'] == ['control_1']
    assert report['completed_case_count'] == 0 and report['scientific_pass'] is None
    case = report['cases'][0]
    assert case['status'] == 'PAUSED_PROTOCOL' and case['accepted_revision'] is None
    assert case['actual_new_version'] is False and case['final_saved_review'] is None
    assert case['targets'][0]['final_saved'] == ['wrong formula']
    assert case['recheck']['prior_findings'][0]['status'] == 'resolved'
    assert case['human_acceptance']['scientific_acceptance'] is None
    assert case['cost']['reserved_cny'] == '1.000000' and case['cost']['spent_upper_cny'] == '0.000000'
    rendered = exporter.render_markdown(report)
    assert 'section_updates[0].value must be an object' in rendered
    assert 'DO_NOT_EXPORT_REASONING' not in json.dumps(report)
    assert '人工验收（待填写）' in rendered


def test_saved_revision_and_routine_rejection_are_facts_not_automatic_scientific_acceptance(tmp_path):
    fixture = setup_run(tmp_path, status='COMPLETED', new_version=True)
    report = exporter.export_controls(tmp_path, 'example', fixture)
    case = report['cases'][0]
    assert case['actual_new_version'] is True
    assert case['targets'][0]['text_changed'] is True
    assert case['final_saved_review']['action'] == 'reject'
    assert case['human_acceptance']['target_error_actually_corrected'] is None
    assert report['all_expected_runs_completed'] is False and report['scientific_pass'] is None


def test_explicit_v1_fixture_and_input_mismatch_are_visible(tmp_path):
    fixture = setup_run(tmp_path)
    data = json.loads(fixture.read_text(encoding='utf-8'))
    del data['fixture_version']
    data['cases'][0]['model_visible']['card']['minimal_test']['measurements'] = ['a different fixture']
    historical = fixture.with_name('scientific_error_pairs_v1.json')
    historical.write_text(json.dumps(data), encoding='utf-8')
    report = exporter.export_controls(tmp_path, 'example', historical)
    assert report['fixture_version'] == 1
    assert report['cases'][0]['fixture_target_input_matches'] is False
    assert exporter.at_path({}, '/absent/0') == {'location_missing': True}
    assert exporter.at_path(['one'], '/-1') == {'location_missing': True}


def test_correct_control_displays_its_paired_error_location_without_changing_expected_label(tmp_path):
    fixture = setup_run(tmp_path)
    data = json.loads(fixture.read_text(encoding='utf-8'))
    data['cases'][0]['expected'].update(target_locations=[], has_target_hard_error=False)
    fixture.write_text(json.dumps(data), encoding='utf-8')
    report = exporter.export_controls(tmp_path, 'example', fixture)
    case = report['cases'][0]
    assert case['targets'][0]['location'] == 'minimal_test.measurements'
    assert case['targets'][0]['original'] == ['wrong formula']
    assert case['targets'][0]['final_saved'] == ['wrong formula']
    assert case['display_locations_origin'] == 'paired_faulty_case_display_only'
    assert case['expected']['target_locations'] == []
    assert case['expected']['has_target_hard_error'] is False
    assert case['human_acceptance']['scientific_acceptance'] is None
    assert '仅用于展示，不改变 expected 标签' in exporter.render_markdown(report)
    assert json.loads(fixture.read_text(encoding='utf-8')) == data
