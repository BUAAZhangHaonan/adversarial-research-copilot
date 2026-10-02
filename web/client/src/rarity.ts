/* 卡牌稀有度推导 + ARC v2 术语中文化映射 */

import type { DiscoveryCard } from './types'

export type Rarity = 'SS' | 'S' | 'A' | 'B' | 'X'

/**
 * 由预研结论推导稀有度：
 * lead（有条件线索）→ SS；discuss（值得讨论）→ S；
 * park（线索搁置）→ B；drop（放弃）→ X；尚未预研 → A（待评估）。
 */
export function rarityOf(card: DiscoveryCard): Rarity {
  const decision = card.note?.decision
  if (decision === 'lead') return 'SS'
  if (decision === 'drop') return 'X'
  if (decision === 'discuss') return 'S'
  if (card.status === 'park') return 'B'
  if (card.status === 'drop') return 'X'
  return 'A'
}

export const RARITY_LABEL: Record<Rarity, string> = {
  SS: 'SS·线索',
  S: 'S·值得讨论',
  A: 'A·待评估',
  B: 'B·线索',
  X: 'X·碎裂',
}

export const RARITY_ORDER: Record<Rarity, number> = { SS: 0, S: 1, A: 2, B: 3, X: 4 }

export function sortCards(cards: DiscoveryCard[]): DiscoveryCard[] {
  return [...cards].sort((a, b) => {
    const ra = RARITY_ORDER[rarityOf(a)] - RARITY_ORDER[rarityOf(b)]
    if (ra !== 0) return ra
    return (b.note?.nearest_work?.length ?? 0) - (a.note?.nearest_work?.length ?? 0)
  })
}

export const DECISION_LABEL: Record<string, string> = {
  lead: '优先讨论',
  discuss: '可以讨论',
  drop: '暂不推进',
}

export const TRIAGE_LABEL: Record<string, string> = {
  investigate: '等待核查',
  park: '搁置线索',
  drop: '暂不推进',
}

export const SKETCH_LABEL: Record<string, string> = {
  submit: '保留这个想法',
  skip: '跳过这个想法',
  stop: '结束本轮召唤',
}

export const IDEA_STATUS_LABEL: Record<string, string> = {
  pending: '等待初步评估',
  park: '线索搁置',
  drop: '已放弃',
  checked: '已有核查记录',
}

/** ARC run 顶层状态 */
export const RUN_STATUS_LABEL: Record<string, string> = {
  RUNNING: '运行中',
  COMPLETED: '已完成',
  PAUSED_BUDGET: '预算暂停',
  PAUSED_EXTERNAL: '等待外部条件',
  PAUSED_PROTOCOL: '输出需要修复',
  PAUSED_SCOPE_CHANGE: '问题范围待调整',
  ERROR: '出错',
  CANCELLED: '已取消',
}

export const ASSESSMENT_LABEL: Record<string, string> = {
  PROMISING: '有前景',
  NEEDS_EVIDENCE: '仍需补充证据',
  REJECTED: '被否决',
  SCOPE_CHANGE_PROPOSED: '建议调整问题范围',
}

/** 常见 stop_reason 中文化（未收录枚举收敛为「已结束」，原文进 tooltip） */
export const STOP_REASON_LABEL: Record<string, string> = {
  user_cancelled_process: '用户取消 · 原始检查点未改写',
  process_interrupted: '进程中断 · 需检查原始状态',
  discover_draws_finished_human_selection: '召唤完成，可以选择感兴趣的想法',
  prestudy_finished_human_decision: '核查完成，可以决定是否继续',
  experiment_required: '需要实验验证',
  experiment_proposed: '方案已成 · 待实验',
  budget_exhausted: '预算耗尽',
  max_draws_reached: '已达到本轮想法数量',
  INVALID_OUTPUT_AFTER_REPAIR: '输出反复不合格',
  STOP_WITH_TOOL_CALLS: '等待完成工具调用',
  critical_source_unavailable: '关键文献暂时无法获取',
  evidence_action_exhausted: '现有证据不足以继续判断',
}

/** 进度事件 task_id 的可读名（如 idea3.triage -> 第 3 抽 · 分诊） */
export function taskLabel(taskId: string): string {
  const m = taskId.match(/^idea(\d+)\.(sketch|triage|check)(\.protocol_retry\d+)?$/)
  if (m) {
    const stage = { sketch: '构思想法', triage: '初步评估', check: '核查想法' }[m[2] as 'sketch' | 'triage' | 'check']
    return `第 ${m[1]} 个想法 · ${stage}${m[3] ? '（重试）' : ''}`
  }
  if (taskId === 'survey' || taskId.endsWith('.survey')) return '领域调查'
  if (taskId.endsWith('.development')) return '方案展开'
  if (taskId.endsWith('.pressure.science.review')) return '科学评审'
  if (taskId.endsWith('.pressure.science.revision')) return '方案修订'
  if (taskId.endsWith('.pressure.science.recheck')) return '复核检查'
  return taskId
}

/** 运行中的一句人话叙事(按最近任务推断当前阶段) */
export function stageNarrative(current: string | null | undefined, mode: string): string {
  if (!current) return mode === 'discover' ? '正在准备任务，随后会调查这个领域。' : '正在准备任务。'
  const m = current.match(/^idea(\d+)\.(sketch|triage|check)$/)
  if (m) {
    const n = m[1]
    if (m[2] === 'sketch') return `正在构思第 ${n} 个研究想法。`
    if (m[2] === 'triage') return `正在初步评估第 ${n} 个想法，判断是否值得继续查证。`
    return `正在核查第 ${n} 个想法的相关工作和实施条件。`
  }
  if (current.endsWith('.survey') || current === 'survey') return '正在查阅相关工作，了解这个领域有哪些问题值得研究。'
  if (current.endsWith('.development')) return '正在把想法展开为方案，并核对相关工作与证据。'
  if (current.endsWith('.prestudy')) return '正在核查这个想法的实施条件与相关工作。'
  if (current.includes('science.review')) return '正在核对方案主张，并查找证据和可能的反例。'
  if (current.includes('science.revision')) return '正在根据核查结果修订方案。'
  if (current.includes('science.recheck')) return '正在复核修订后的方案。'
  if (current.endsWith('.polish')) return '正在整理本轮结果，使内容更便于阅读。'
  return ''
}

export const MODE_LABEL: Record<string, string> = {
  discover: '召唤',
  develop: '试炼',
  debate: '审判',
  resume: '续跑',
}

export function fmtCNY(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return '—'
  return `¥${n.toFixed(digits)}`
}

export function fmtTokens(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

export function fmtDuration(fromIso: string, toIso?: string | null): string {
  const from = new Date(fromIso).getTime()
  const to = toIso ? new Date(toIso).getTime() : Date.now()
  const s = Math.max(0, Math.round((to - from) / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m${s % 60}s`
  return `${Math.floor(m / 60)}h${m % 60}m`
}

export function fmtTime(unix: number): string {
  const d = new Date(unix * 1000)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function fmtIso(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** 相对时间：3 天前 / 5 小时前 / 12 分钟前 */
export function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return '—'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return '—'
  const diff = Math.max(0, Date.now() - t) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} 天前`
  return fmtIso(iso)
}
