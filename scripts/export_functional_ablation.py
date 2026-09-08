"""Read-only A–E artifact export; no DB access, model calls or quality verdicts."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re


def differences(before, after, path=''):
    if isinstance(before, dict) and isinstance(after, dict):
        return [change for key in sorted(before.keys() | after.keys())
                for change in differences(before.get(key), after.get(key), path + '/' + key)]
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [change for index, (a, b) in enumerate(zip(before, after))
                for change in differences(a, b, path + '/' + str(index))]
    return [] if before == after else [{'location': path, 'before': before, 'after': after}]


def brief_review(value):
    if not isinstance(value, dict):
        return None
    keys = ('action', 'selection', 'assessment', 'value_judgment', 'value_reason',
            'why_worth_investigating', 'closest_work_delta', 'test_identifiability',
            'decisive_findings', 'prior_findings', 'remaining_uncertainty', 'decisive_risks',
            'unverified_assumptions', 'next_action')
    return {key: value[key] for key in keys if key in value}


def cost_summary(conditions, judge_cost):
    accounts, missing = {}, []
    for stage, value in [*( (key, arm.get('cost')) for key, arm in conditions.items()), ('judge', judge_cost)]:
        if not isinstance(value, dict):
            missing.append(stage)
            continue
        account = value.get('account_id') or stage
        if account in accounts and accounts[account] != value:
            raise ValueError('CONFLICTING_COST_SNAPSHOTS_FOR_ACCOUNT')
        accounts[account] = value
    fields = ('spent_lower_cny', 'spent_upper_cny', 'reserved_cny', 'unsettled_lower_cny')
    totals = {}
    missing_fields = {}
    for field in fields:
        unknown = [account for account, cost in accounts.items() if cost.get(field) is None]
        subtotal = sum((Decimal(str(cost[field])) for cost in accounts.values() if cost.get(field) is not None), Decimal('0'))
        totals[field] = format(subtotal, '.6f')
        if unknown:
            missing_fields[field] = unknown
    return {'known_subtotal': totals, 'included_account_ids': list(accounts),
            'missing_stage_costs': missing, 'missing_cost_fields': missing_fields,
            'unknown_calls': sum(cost.get('unknown_calls', 0) for cost in accounts.values()),
            'all_stage_costs_recorded': not missing and not missing_fields,
            'basis': 'Distinct A–E child accounts plus judge only; parent historical spending is excluded. Missing costs are unknown, not zero.'}


def restore_evaluation(item):
    mapping = item.get('identity_map_private') or {}
    value = item.get('evaluation') or {}
    restored = []
    for finding in value.get('per_candidate_findings', []):
        anonymous = finding.get('candidate_id')
        restored.append({**finding, 'system': (mapping.get(anonymous) or {}).get('system')})
    preference = value.get('preference_if_requested')
    def label(match):
        identifier = match.group()
        system = (mapping.get(identifier) or {}).get('system')
        return f'{system} [{identifier}]' if system else identifier
    return {'order': item.get('order'), 'identity_map': mapping, 'candidate_findings': restored,
            'preference_original': preference,
            'preference_with_system_labels': re.sub(r'\bcandidate_\d+\b', label, preference) if isinstance(preference, str) else preference,
            **{key: value.get(key) for key in ('decisive_errors', 'supported_strengths', 'unresolved_verifications', 'uncertainty')}}


def export_ablation(data_dir, experiment_id):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', experiment_id) or '..' in experiment_id:
        raise ValueError('INVALID_EXPERIMENT_ID')
    root = Path(data_dir) / 'artifacts' / 'functional-evaluations' / experiment_id
    manifest_path, report_path = root / 'manifest.json', root / 'report.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.is_file() else {}
    material = manifest.get('material') or {}
    original_task = material.get('original_task') or {'topic': material.get('topic'), 'boundaries': material.get('boundaries', [])}
    arms = report.get('conditions') or {}
    conditions = {}
    for key in 'ABCDE':
        arm = arms.get(key) or {}
        draft = arm.get('draft')
        conditions[key] = {'design': manifest.get('conditions', {}).get(key), 'run_id': arm.get('run_id'),
            'status': arm.get('status', 'NOT_RECORDED'), 'stop_reason': arm.get('stop_reason'),
            'not_run_reason': arm.get('not_run_reason'), 'candidate_present': isinstance(draft, dict),
            'candidate_origin': arm.get('candidate_origin'), 'initial_review_origin': arm.get('initial_review_origin'),
            'card_version': arm.get('card_version'), 'cost': arm.get('cost'),
            'card': {field: draft.get(field) for field in ('title', 'problem_anchor', 'contribution', 'motivation', 'minimal_test', 'risks')} if isinstance(draft, dict) else None,
            'review_type': 'legacy_selector' if key in 'ABC' else 'scientific_review',
            'review': brief_review(arm.get('judgment'))}
    a, d, e = (arms.get(key) or {} for key in 'ADE')
    same = a['draft'] == d['draft'] if isinstance(a.get('draft'), dict) and isinstance(d.get('draft'), dict) else None
    e_changes = differences(a['draft'], e['draft']) if isinstance(a.get('draft'), dict) and isinstance(e.get('draft'), dict) else None
    initial_origin = e.get('initial_review_origin')
    reuse = initial_origin.startswith(experiment_id + '.D.') if isinstance(initial_origin, str) else None
    return {'experiment_id': experiment_id, 'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_artifacts': {'manifest': str(manifest_path.resolve()), 'report': str(report_path.resolve())},
            'status': report.get('status', 'NOT_RECORDED'), 'stop_reason': report.get('stop_reason'),
            'judge_status': report.get('judge_status', 'NOT_RECORDED'), 'judge_cost': report.get('judge_cost'),
            'original_task': original_task, 'conditions': conditions,
            'material_summary': {'source_count': len(material.get('sources', [])), 'evidence_count': len(material.get('evidence', [])),
                                 'seed': manifest.get('seed'), 'source_run_id': manifest.get('source_run_id')},
            'reuse': {'A_D_drafts_equal': same, 'E_initial_review_origin': initial_origin,
                      'E_initial_review_recorded_as_D': reuse, 'E_candidate_origin': e.get('candidate_origin')},
            'E_changes_from_A': e_changes, 'evaluations': [restore_evaluation(item) for item in report.get('evaluations', [])],
            'experiment_cost': cost_summary(conditions, report.get('judge_cost')),
            'quality_improved': None, 'human_judgment': {'preferred_condition': None, 'research_value_improved': None,
                'scientific_correction_effective': None, 'order_effect': None, 'reasons_and_limits': ''},
            'limits': ['A/D 按设计共享候选，E 按设计复用 D 初审；实际记录单列核对。',
                       'E 字段变化只证明产物不同，不自动证明修订正确或研究价值提高。',
                       '双序匿名自动评价提供比较理由，不等于领域专家认可；未完成、无候选和失败均保留。']}


def render_markdown(summary):
    def block(value):
        return '```json\n' + json.dumps(value, ensure_ascii=False, indent=2) + '\n```'
    lines = ['# A–E 功能消融结果', '', f"实验 `{summary['experiment_id']}`：{summary['status']}；评价阶段：{summary['judge_status']}。", '',
             '原始问题与用户条件：', block(summary['original_task']), '',
             '本实验费用（仅独立 A–E 子账户及 judge；不含父账本历史费用）：', block(summary['experiment_cost']), '',
             '；'.join(summary['limits']), '', '## 候选与审查', '']
    for key, arm in summary['conditions'].items():
        lines += [f"### {key} · {arm['design'] or '设计未记录'}", '',
                  f"状态：{arm['status']}；停因：{arm['stop_reason'] or arm['not_run_reason'] or '无记录'}。",
                  '阶段费用：' + json.dumps(arm['cost'], ensure_ascii=False), '']
        card = arm['card']
        if card is None:
            lines += ['本阶段尚无可展示候选。', '']
        else:
            lines += [card.get('title') or '未命名候选', '', '卡片问题：', block(card.get('problem_anchor')),
                      '核心洞察与研究决定：', block(card.get('contribution')),
                      '最小检验：', block(card.get('minimal_test')), '关键风险：', block(card.get('risks')), '']
        lines += ['审查类型：' + arm['review_type'], block(arm['review']), '']
    lines += ['## 候选与初审复用', '', block(summary['reuse']), '', '## E 相对 A 的实际字段变化', '']
    changes = summary['E_changes_from_A']
    if changes is None:
        lines += ['缺少 A 或 E 的候选，暂不能比较实际修改。', '']
    elif not changes:
        lines += ['已保存候选没有字段变化；不据此推断修订是否必要。', '']
    else:
        lines += [f'共 {len(changes)} 处变化；下列展示前 12 处，完整变化保留在同名 JSON 摘要。', '']
        for change in changes[:12]:
            lines += [f"位置 `{change['location']}`", block(change), '']
    lines += ['## 双序匿名评价（已还原系统映射）', '']
    for evaluation in summary['evaluations']:
        lines += [f"### {evaluation['order']}", '', block(evaluation), '']
    if not summary['evaluations']:
        lines += ['尚无已保存的匿名评价。', '']
    lines += ['## 人工判断（待填写）', '', '- 哪一条件值得优先研究：', '- 研究价值是否提高及依据：',
              '- 科学纠错是否有效及依据：', '- 顺序影响与其他限制：', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--experiment-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.suffix.lower() != '.md':
        parser.error('--output must end in .md')
    summary = export_ablation(args.data_dir, args.experiment_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(summary), encoding='utf-8')
    args.output.with_suffix('.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'experiment_id': summary['experiment_id'], 'status': summary['status'],
                      'quality_improved': summary['quality_improved']}))


if __name__ == '__main__':
    main()
