import { useEffect, useState } from 'react'
import type { JobStatus } from '../types'
import TaskFeed from './TaskFeed'
import RitualCircle from './RitualCircle'
import { BudgetDial, ElapsedBlock, DrawDial } from './Dials'
import { stageNarrative } from '../rarity'

/** 试炼 / 审判运行页：法阵 + 双仪表 + 阶段叙事 + 任务流水 */
export default function StageRunning({ title, glyph, status, elapsed, jobId, onCancel, hint, error, onReset }: {
  title: string
  glyph: string
  status: JobStatus | null
  elapsed: number
  jobId: string | null
  onCancel: () => Promise<unknown>
  hint: string
  error?: string
  onReset?: () => void
}) {
  const [showLog, setShowLog] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [cancelError, setCancelError] = useState('')
  useEffect(() => { setCancelError(''); setCancelling(false) }, [jobId])
  const cancel = async () => {
    if (cancelling) return
    setCancelling(true)
    setCancelError('')
    try { await onCancel() } catch (e) { setCancelError(String(e)) }
    finally { setCancelling(false) }
  }
  const jobStatus = status?.job.status
  const failed = jobStatus === 'failed' || jobStatus === 'cancelled'
  const paused = jobStatus === 'paused'
  const running = jobStatus === 'running'
  const p = status?.progress
  const circleState = failed ? 'failed' : paused ? 'paused' : 'done'
  const narrative = failed ? '任务未完成，请查看下方的原因。' : paused ? '任务已暂停，查看结果了解原因与恢复方式。' : jobStatus === 'completed' ? '本轮已完成，可以查看结果、相关证据和仍需核查的问题。' : stageNarrative(p?.current, status?.job.mode ?? 'develop')
  const rounds = p?.rounds_completed ?? 0

  return (
    <div className={`page stage-${status?.job.mode || 'develop'}`} style={{ maxWidth: 940 }}>
      <div className="panel ritual-stage">
        <h2 className={`pixel-big ritual-title ${failed ? 'rt-failed' : paused ? 'rt-paused' : 'rt-running'}`}>
          {failed ? `✗ ${title}中断` : paused ? `⏸ ${title}暂停` : jobStatus === 'completed' ? `${title}已结束` : status ? `${title}进行中` : '正在读取任务状态…'}
        </h2>
        <p className="ritual-narrative">{narrative}</p>

        <div className="ritual-deck">
          <DrawDial started={rounds} max={0} active={running} />
          <RitualCircle size={196} state={running ? 'running' : circleState} core={glyph} />
          <BudgetDial
            spent={p?.budget?.spent_upper_cny ?? null}
            reserved={p?.budget?.reserved_cny ?? null}
            limit={p?.budget?.limit_cny ?? null}
          />
        </div>

        <div className="ritual-foot">
          <ElapsedBlock seconds={elapsed} />
          <span style={{ flex: 1 }} />
          <span className="pixel small muted">{jobId}</span>
        </div>
        {p?.budget?.total_cost_complete === false && <p className="small muted">部分调用费用尚未计入，总费用待确认。</p>}

        <div className="ritual-feed">
          <div className="pixel small muted" style={{ marginBottom: 6 }}>最近完成的步骤</div>
          <TaskFeed tasks={p?.tasks ?? []} current={p?.current} max={4} />
        </div>

        <p className="muted small" style={{ maxWidth: 560, margin: '12px auto' }}>{hint}</p>
        {(error || cancelError) && <p className="error-text" role="alert">{cancelError ? `终止失败：${cancelError}` : `状态暂时无法更新：${error}，正在重试。`}</p>}

        {status && !running && status.job.error && (
          <div className="speech" style={{ textAlign: 'left', color: 'var(--red)', maxHeight: 160, fontSize: 12 }}>
            {status.job.error.slice(-800)}
          </div>
        )}

        <div className="ritual-actions">
          {running ? (
            <button className="btn btn-red" disabled={cancelling} onClick={cancel}>{cancelling ? '终止中…' : '终止'}</button>
          ) : status?.job.run_dir ? (
            <a className="btn" href={`#/runs/${status.job.run_dir}`}>查看结果 →</a>
          ) : null}
          {status && !running && onReset && <button className="btn btn-ghost" onClick={onReset}>新开一轮</button>}
          <button className="btn btn-ghost" onClick={() => setShowLog(!showLog)}>
            {showLog ? '收起日志' : '日志'}
          </button>
        </div>
        {showLog && (
          <div className="speech mono" style={{ marginTop: 14, textAlign: 'left', maxHeight: 260, fontSize: 12 }}>
            {status?.log_tail || '(还没有输出)'}
          </div>
        )}
      </div>
    </div>
  )
}
