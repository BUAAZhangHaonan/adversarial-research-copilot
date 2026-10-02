import type { RunMeta, RunSummary } from '../types'
import { ASSESSMENT_LABEL, RUN_STATUS_LABEL, STOP_REASON_LABEL } from '../rarity'

/** ARC run 状态徽章（含 job 状态兼容） */
export function RunStatusBadge({ status, stopReason, pulse = false }: {
  status?: string | null
  stopReason?: string | null
  pulse?: boolean
}) {
  if (!status) return null
  const variant = status === 'COMPLETED' || status === 'completed' ? 'ok'
    : status.startsWith('PAUSED') || status === 'paused' ? 'warn'
    : status === 'ERROR' || status === 'failed' ? 'bad'
    : status === 'RUNNING' || status === 'running' ? 'warn'
    : ''
  const label = RUN_STATUS_LABEL[status] ?? status
  const tip = stopReason ?? undefined
  return (
    <span className={`chip ${variant} ${pulse ? 'chip-pulse' : ''}`} title={tip}>
      {pulse && <span className="dot-live" />}
      {label}
      {stopReason && stopReason !== status && (
        <span className="chip-sub"> · {STOP_REASON_LABEL[stopReason] ?? '已结束'}</span>
      )}
    </span>
  )
}

/** 评估结论徽章：PROMISING / NEEDS_EVIDENCE / REJECTED / SCOPE_CHANGE_PROPOSED */
export function AssessmentBadge({ assessment }: { assessment?: string | null }) {
  if (!assessment) return null
  const variant = assessment === 'PROMISING' ? 'gold'
    : assessment === 'NEEDS_EVIDENCE' ? 'info'
    : assessment === 'REJECTED' ? 'bad'
    : 'warn'
  return (
    <span className={`chip ${variant} chip-assess a-${assessment.toLowerCase()}`}>
      {ASSESSMENT_LABEL[assessment] ?? assessment}
    </span>
  )
}

export function shortReason(reason: string, n = 36): string {
  return reason.length > n ? `${reason.slice(0, n)}…` : reason
}

export function RunBadges({ run, pulse = false }: { run: RunMeta | RunSummary; pulse?: boolean }) {
  return (
    <>
      <RunStatusBadge status={run.status} stopReason={run.stop_reason} pulse={pulse} />
      <AssessmentBadge assessment={run.assessment} />
    </>
  )
}
