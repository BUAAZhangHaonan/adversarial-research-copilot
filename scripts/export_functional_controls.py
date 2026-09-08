"""Export scientific-control evidence from a read-only SQLite snapshot.

No model calls, Store initialization, schema migrations or verdict inference.
--fixture is required: historical v1 results must not use the corrected v2 inputs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from arc.budget import BudgetLedger


def at_path(value, path):
    """Resolve fixture dot paths or review JSON Pointers without guessing keys."""
    parts = path[1:].split('/') if path.startswith('/') else path.split('.')
    for part in parts:
        part = part.replace('~1', '/').replace('~0', '~')
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return {'location_missing': True}
    return value


def accepted_stage(state, tasks, key):
    if isinstance(state.get(key), dict):
        return state[key]
    for task in reversed(tasks):
        suffix = task['task_id'].split('.science.', 1)[-1]
        logical_suffix = key.removeprefix('science.')
        if not (suffix == logical_suffix or suffix.startswith(logical_suffix + '.')):
            continue
        envelope = task.get('accepted_result')
        if task.get('status') == 'ACCEPTED' and isinstance(envelope, dict) and isinstance(envelope.get('result'), dict):
            return envelope['result']
    return None


def review_summary(review):
    if not isinstance(review, dict):
        return None
    keys = ('original_question', 'scope_faithful', 'core_insight', 'value_judgment', 'value_reason',
            'action', 'decisive_findings', 'verification_work', 'prior_findings', 'remaining_uncertainty')
    return {key: review[key] for key in keys if key in review}


def export_controls(data_dir, prefix, fixture_path):
    data_dir, fixture_path = Path(data_dir), Path(fixture_path)
    fixture = json.loads(fixture_path.read_text(encoding='utf-8'))
    version = fixture.get('fixture_version')
    if version is None and fixture_path.name == 'scientific_error_pairs_v1.json':
        version = 1
    if version is None:
        raise ValueError('FIXTURE_VERSION_REQUIRED: use the explicit historical v1 file or a versioned fixture')
    database = (data_dir / 'arc.sqlite').resolve()
    if not database.is_file():
        raise FileNotFoundError(database)
    result = {'generated_at': datetime.now(timezone.utc).isoformat(), 'prefix': prefix,
              'fixture_path': str(fixture_path.resolve()), 'fixture_version': version,
              'expected_case_count': len(fixture['cases']), 'present_case_count': 0,
              'completed_case_count': 0, 'missing_case_ids': [], 'cases': [],
              'scientific_pass': None,
              'interpretation': '结构状态、文字变化和模型自报结论都不等于科学验收；人工验收栏留空。'}
    db = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute('BEGIN')  # One consistent read snapshot while the runner may continue.
        for index, case in enumerate(fixture['cases'], 1):
            run_id = f'{prefix}.case{index}'
            row = db.execute('SELECT data FROM runs WHERE id=?', (run_id,)).fetchone()
            if row is None:
                result['missing_case_ids'].append(case['case_id'])
                continue
            run = json.loads(row['data'])
            state = run.get('state', {})
            tasks = [json.loads(row['data']) for row in db.execute('SELECT data FROM tasks WHERE run_id=? ORDER BY rowid', (run_id,))]
            cards = [json.loads(row['data']) for row in db.execute('SELECT data FROM cards WHERE card_id=? ORDER BY version', (run.get('card_id'),))]
            current = next((card for card in cards if card['version'] == run.get('card_version')), None)
            inputs = state.get('task_inputs', {}).get('science.review', {}).get('payload', {})
            original = inputs.get('review_target') or (cards[0]['draft'] if cards else None)
            final = current['draft'] if current else None
            initial_review = accepted_stage(state, tasks, 'science.review')
            revision = accepted_stage(state, tasks, 'science.revision')
            recheck = accepted_stage(state, tasks, 'science.recheck')
            support_review = accepted_stage(state, tasks, 'science.support_review')
            latest_review = support_review or recheck or initial_review
            resolutions = {item.get('finding_id'): item for item in (latest_review or {}).get('prior_findings', []) if isinstance(item, dict)}
            original_findings = (initial_review or {}).get('decisive_findings', [])
            unresolved = [{'finding': finding, 'latest_model_resolution': resolutions.get(finding.get('finding_id'))}
                          for finding in original_findings
                          if resolutions.get(finding.get('finding_id'), {}).get('status') not in {'resolved', 'reviewer_error'}]
            targets = [{'location': path, 'original': at_path(original, path), 'final_saved': at_path(final, path),
                        'text_changed': at_path(original, path) != at_path(final, path)}
                       for path in case['expected']['target_locations']]
            alignment = all(target['original'] == at_path(case['model_visible']['card'], target['location']) for target in targets)
            alignment = alignment and (original or {}).get('problem_anchor', {}).get('question') == case['model_visible']['card']['problem_anchor']['question']
            account = run.get('budget_account_id')
            cost = BudgetLedger.__new__(BudgetLedger)._summary(db, account) if account else None
            task_summary = []
            for task in tasks:
                item = {key: task.get(key) for key in ('task_id', 'status', 'error', 'response_artifact_path', 'created_at', 'updated_at')}
                if isinstance(item['error'], str) and len(item['error']) > 4000:
                    item['error'] = item['error'][:4000] + ' [truncated; see response artifact]'
                item['run_completed_after_recorded_failure'] = run['status'] == 'COMPLETED' and task.get('status') in {'ERROR', 'PAUSED_PROTOCOL', 'PAUSED_EXTERNAL', 'UNKNOWN'}
                task_summary.append(item)
            initial_version = inputs.get('card', {}).get('version') if isinstance(inputs.get('card'), dict) else None
            initial_version = initial_version or (cards[0]['version'] if cards else None)
            result['cases'].append({
                'case_id': case['case_id'], 'pair_id': case['pair_id'], 'run_id': run_id,
                'status': run['status'], 'stop_reason': run.get('stop_reason'),
                'fixture_target_input_matches': alignment, 'expected': case['expected'],
                'original_card_version': initial_version, 'final_saved_card_version': run.get('card_version'),
                'actual_new_version': bool(initial_version is not None and run.get('card_version') is not None and run['card_version'] > initial_version),
                'original_card': original, 'final_saved_card': final, 'targets': targets,
                'initial_review': review_summary(initial_review),
                'accepted_revision': {key: revision[key] for key in ('section_updates', 'claim_updates', 'remove_claim_ids', 'addressed_findings', 'change_summary', 'abandon') if key in revision} if revision else None,
                'recheck': review_summary(recheck), 'support_review': review_summary(support_review),
                'review_scope_note': '复核可能针对尚未保存的拟议修订；以 final_saved_card 和对应 final_saved_review 判断实际落地内容。',
                'final_saved_review': review_summary(state.get('final_scientific_review'))
                    if state.get('final_scientific_card_version') == run.get('card_version') else None,
                'initial_findings_without_model_resolution': unresolved,
                'latest_model_findings': (latest_review or {}).get('decisive_findings', []),
                'tasks': task_summary, 'cost': cost,
                'human_acceptance': {'target_error_detected': None, 'target_error_actually_corrected': None,
                                     'correct_control_false_positive': None, 'scientific_acceptance': None, 'notes': ''},
            })
        db.rollback()
    finally:
        db.close()
    result['present_case_count'] = len(result['cases'])
    result['completed_case_count'] = sum(case['status'] == 'COMPLETED' for case in result['cases'])
    result['all_expected_runs_completed'] = result['completed_case_count'] == result['expected_case_count']
    return result


def render_markdown(report):
    def block(value):
        return '```json\n' + json.dumps(value, ensure_ascii=False, indent=2) + '\n```\n'
    lines = ['# 科学纠错真实运行证据', '',
             f"Fixture v{report['fixture_version']}：`{report['fixture_path']}`", '',
             f"运行前缀：`{report['prefix']}`；快照时间：{report['generated_at']}", '',
             f"已存在 {report['present_case_count']}/{report['expected_case_count']} 例，运行 COMPLETED {report['completed_case_count']} 例。",
             'COMPLETED 仅表示工作流结束；文字改动、位置命中、模型 retain/reject 均不能替代科学验收。', '',
             '缺少的样例：' + ('、'.join(report['missing_case_ids']) or '无'), '']
    if report['fixture_version'] == 1:
        lines += ['v1 为保留的开发原件，其中正确目标字段仍可能伴随其他实质问题；不能将额外查错直接统计为误杀。', '']
    for case in report['cases']:
        lines += [f"## {case['case_id']}", '',
                  f"Run `{case['run_id']}`：{case['status']}；停因：{case['stop_reason'] or '无'}。",
                  f"实际卡版本：{case['original_card_version']} → {case['final_saved_card_version']}；有实际新版本：{case['actual_new_version']}。",
                  f"fixture 原题和目标原句匹配：{case['fixture_target_input_matches']}。", '',
                  case['review_scope_note'], '', '对照预期（人工判读用，未发给模型）：', block(case['expected']),
                  '费用（账本估计与保留额，CNY）：', block(case['cost']),
                  '### 目标原句与当前已保存句', '']
        for target in case['targets']:
            lines += [f"位置 `{target['location']}`；文字变化：{target['text_changed']}", '',
                      '原句：', block(target['original']), '当前已保存句：', block(target['final_saved'])]
        for title, key in [('初审具体判断及依据', 'initial_review'), ('已接受的修订（不保证已落地）', 'accepted_revision'),
                           ('修订复核', 'recheck'), ('补证复核', 'support_review'), ('当前保存版本的最终判断', 'final_saved_review'),
                           ('初审尚无模型解决记录的缺陷', 'initial_findings_without_model_resolution'),
                           ('最近审核提出的缺陷', 'latest_model_findings'), ('任务状态与原件入口', 'tasks')]:
            lines += [f'### {title}', '', block(case[key])]
        lines += ['### 人工验收（待填写）', '',
                  '- 目标错误是否发现：', '- 目标错误是否实际消除：', '- 正确对照是否误杀：',
                  '- 科学验收结论：', '- 依据与限制：', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Markdown path; JSON is written beside it')
    args = parser.parse_args()
    if args.output.suffix.lower() != '.md':
        parser.error('--output must end in .md')
    report = export_controls(args.data_dir, args.prefix, args.fixture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(report), encoding='utf-8')
    args.output.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('fixture_version', 'present_case_count', 'completed_case_count', 'all_expected_runs_completed', 'scientific_pass')}))


if __name__ == '__main__':
    main()
