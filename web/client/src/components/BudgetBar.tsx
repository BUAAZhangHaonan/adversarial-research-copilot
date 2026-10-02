import type { BudgetProgress, CostSummary } from '../types'
import { fmtCNY } from '../rarity'

interface Props {
  budget?: BudgetProgress | null
  cost?: CostSummary | null
  /** 紧凑模式（运行页小条） */
  compact?: boolean
}

/** 预算燃烧条：已结算 + 预留 相对授权上限的占比 */
export default function BudgetBar({ budget, cost, compact = false }: Props) {
  const b = budget ?? cost ?? null
  if (!b || b.limit_cny == null || b.limit_cny <= 0) return null
  const spent = (b.spent_upper_cny ?? b.spent_lower_cny ?? 0) as number
  const reserved = Math.max(0, (b.reserved_cny ?? 0) as number)
  const limit = b.limit_cny
  const spentPct = Math.min(100, (spent / limit) * 100)
  const reservedPct = Math.min(100 - spentPct, (reserved / limit) * 100)
  const burnedPct = spentPct + reservedPct
  const hot = burnedPct >= 80

  return (
    <div className={`budget-bar ${hot ? 'budget-hot' : ''} ${compact ? 'budget-compact' : ''}`}>
      <div className="budget-track">
        <div className="budget-spent" style={{ width: `${spentPct}%` }} />
        <div className="budget-reserved" style={{ left: `${spentPct}%`, width: `${reservedPct}%` }} />
        {burnedPct > 0.5 && burnedPct < 100 && (
          <div className="budget-shimmer" style={{ width: `${Math.min(burnedPct, 100)}%` }} />
        )}
      </div>
      <div className="budget-meta pixel">
        <span title="已知费用的已结算上界">已结算 {fmtCNY(spent, 2)}</span>
        {reserved > 0 && <span title="进行中任务的预留">+ 预留 {fmtCNY(reserved)}</span>}
        <span className="budget-limit" title="授权上限">/ {fmtCNY(limit, 0)}</span>
        <span style={{ flex: 1 }} />
        {b.call_count != null && <span className="muted">{b.call_count} 次调用</span>}
      </div>
      {(b.total_cost_complete === false || (b.unknown_calls ?? 0) > 0 || (b.unmetered_calls ?? 0) > 0) && (
        <p className="small cost-incomplete" role="status">{b.cost_scope === 'report_snapshot'
          ? '费用来自报告快照，完整计价范围尚未确认。'
          : '部分调用费用尚未计入，总费用待确认。'}</p>
      )}
    </div>
  )
}
