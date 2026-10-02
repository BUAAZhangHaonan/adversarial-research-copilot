import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { api, ApiError } from '../api'
import type { DiscoverDetail, DiscoveryCard } from '../types'
import { rarityOf, sortCards } from '../rarity'
import IdeaCardView from '../components/IdeaCard'
import TaskFeed from '../components/TaskFeed'
import RitualCircle from '../components/RitualCircle'
import { BudgetDial, DrawDial, ElapsedBlock } from '../components/Dials'
import { stageNarrative } from '../rarity'
import { useElapsed, useJob } from '../hooks'

const TIERS = [
  { key: 'quick', label: '快抽', desc: '2 张 · 预算 ¥10', draws: 2, budget: 10 },
  { key: 'std', label: '标准', desc: '3 张 · 预算 ¥16', draws: 3, budget: 16 },
  { key: 'abyss', label: '深渊', desc: '5 张 · 预算 ¥28', draws: 5, budget: 28 },
]

type Phase = 'form' | 'running' | 'result'

export default function Summon() {
  const [phase, setPhase] = useState<Phase>('form')
  const [topic, setTopic] = useState((useLocation().state as { topic?: string } | null)?.topic ?? '')
  const [tier, setTier] = useState(TIERS[1])
  const [search, setSearch] = useSearchParams()
  const jobId = search.get('job')
  const [submitError, setSubmitError] = useState('')
  const [busy, setBusy] = useState(false)
  const [detail, setDetail] = useState<DiscoverDetail | null>(null)
  const [resultError, setResultError] = useState('')
  const [retry, setRetry] = useState(0)
  const submitting = useRef(false)

  const { status, error: pollError } = useJob(jobId)
  const elapsed = useElapsed(status?.job.created_at, status?.job.finished_at)

  const reset = () => {
    setSearch({}, { replace: true })
    setDetail(null)
    setResultError('')
    setPhase('form')
  }
  useEffect(() => {
    setDetail(null)
    setResultError('')
    setPhase(jobId ? 'running' : 'form')
  }, [jobId])

  useEffect(() => {
    let alive = true
    if (status?.job.status === 'completed' && status.job.run_dir) {
      setResultError('')
      api.runDetail(status.job.run_dir)
        .then((d) => {
          if (!alive) return
          if (d.mode !== 'discover') throw new Error('任务结果不是召唤记录')
          setDetail(d)
          setPhase('result')
        })
        .catch((e) => { if (alive) { setResultError(String(e)); setPhase('result') } })
    }
    return () => { alive = false }
  }, [status, retry])

  const submit = async () => {
    if (submitting.current || jobId || topic.trim().length < 8) return
    submitting.current = true
    setBusy(true)
    setSubmitError('')
    try {
      const r = await api.submitJob('discover', { topic, draws: tier.draws, budget_cny: tier.budget })
      setSearch({ job: r.job_id }, { replace: true })
      setPhase('running')
    } catch (e) {
      setSubmitError(e instanceof ApiError ? e.message : '提交失败')
    } finally {
      setBusy(false)
      submitting.current = false
    }
  }

  if (!jobId) {
    return (
      <div className="page page-form stage-discover" style={{ maxWidth: 760 }}>
        <div className="panel" style={{ padding: '26px 28px' }}>
          <h2 className="panel-title" style={{ fontSize: 18 }}>🔮 召唤</h2>
          <p className="muted small" style={{ marginTop: 0 }}>
            先了解你关注的领域，再构思研究想法，并对值得继续的候选进行核查。
            你可以选择想法数量和预算上限，运行过程中会显示已知费用。
          </p>
          <textarea
            className="textarea"
            placeholder="写一个你在意的领域，或一个你怀疑没人做对的问题。&#10;例：多模态模型什么时候该主动要更多信息？"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            style={{ minHeight: 128 }}
          />
          <div style={{ display: 'flex', gap: 12, margin: '16px 0', flexWrap: 'wrap' }}>
            {TIERS.map((t) => (
              <button
                key={t.key}
                className={`btn ${tier.key === t.key ? '' : 'btn-ghost'}`}
                style={{ flexDirection: 'column', gap: 3, padding: '10px 18px' }}
                onClick={() => setTier(t)}
              >
                <span>{t.label}</span>
                <span style={{ fontSize: 11, opacity: 0.95 }}>{t.desc}</span>
              </button>
            ))}
          </div>
          {submitError && <div className="error-text pixel" style={{ marginBottom: 10 }}>✗ {submitError}</div>}
          <button className="btn btn-lg" disabled={busy || topic.trim().length < 8} onClick={submit}>
            {busy ? '正在提交…' : `开始召唤 · ${tier.draws} 张`}
          </button>
        </div>
      </div>
    )
  }

  if (phase !== 'result') {
    return (
      <RitualScene
        status={status}
        elapsed={elapsed}
        jobId={jobId}
        onCancel={() => api.cancelJob(jobId)}
        error={pollError}
        onReset={reset}
      />
    )
  }

  if (resultError) return <div className="page"><div className="panel"><p className="error-text" role="alert">结果读取失败：{resultError}</p><button className="btn" onClick={() => setRetry((n) => n + 1)}>重试读取</button></div></div>
  return <PackOpening detail={detail} jobId={jobId} failed={status?.job.status === 'failed'} onReset={reset} />
}

/* ---------------- 召唤进行中 ---------------- */

function RitualScene({ status, elapsed, jobId, onCancel, error, onReset }: {
  status: ReturnType<typeof useJob>['status']
  elapsed: number
  jobId: string | null
  onCancel: () => Promise<unknown>
  error: string
  onReset: () => void
}) {
  const [showLog, setShowLog] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [cancelError, setCancelError] = useState('')
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
  const circleState = failed ? 'failed' : paused ? 'paused' : 'done'
  const p = status?.progress
  const draws = p?.draws
  const budget = p?.budget
  const narrative = failed ? '任务未完成，请查看下方的原因。' : paused ? '任务已暂停，查看结果了解原因与恢复方式。' : jobStatus === 'completed' ? '召唤已结束，正在整理结果。' : stageNarrative(p?.current, 'discover')

  return (
    <div className="page" style={{ maxWidth: 940 }}>
      <div className="panel ritual-stage">
        {[...Array(5)].map((_, i) => (
          <span
            key={i}
            className="pixel"
            style={{
              position: 'absolute',
              left: `${10 + i * 19}%`,
              top: `${10 + (i % 3) * 26}%`,
              fontSize: 18 + (i % 3) * 7,
              opacity: 0.1,
              animation: `floaty ${3 + i * 0.5}s ease-in-out ${i * 0.4}s infinite`,
              pointerEvents: 'none',
            }}
          >
            {['📜', '📖', '📄'][i % 3]}
          </span>
        ))}

        <h2 className={`pixel-big ritual-title ${failed ? 'rt-failed' : paused ? 'rt-paused' : 'rt-running'}`}>
          {failed ? '✗ 召唤未完成' : paused ? '⏸ 暂停' : '🔮 召唤中'}
        </h2>
        <p className="ritual-narrative">{narrative}</p>
        {(error || cancelError) && <p className="error-text" role="alert">{cancelError ? `取消失败：${cancelError}` : `状态暂时无法更新：${error}，正在重试。`}</p>}

        <div className="ritual-deck">
          <DrawDial started={draws?.started ?? 0} max={draws?.max ?? 0} active={running} />
          <RitualCircle size={196} state={running ? 'running' : circleState} core="🔮" />
          <BudgetDial
            spent={budget?.spent_upper_cny ?? null}
            reserved={budget?.reserved_cny ?? null}
            limit={budget?.limit_cny ?? null}
          />
        </div>

        <div className="ritual-foot">
          <ElapsedBlock seconds={elapsed} />
          <span style={{ flex: 1 }} />
          <span className="pixel small muted">{jobId}</span>
        </div>
        {budget?.total_cost_complete === false && <p className="small muted">部分调用费用尚未计入，总费用待确认。</p>}

        <div className="ritual-feed">
          <div className="pixel small muted" style={{ marginBottom: 6 }}>最近完成的步骤</div>
          <TaskFeed tasks={p?.tasks ?? []} current={p?.current} max={4} />
        </div>

        {running && <p className="muted small" style={{ marginTop: 12 }}>每个想法都需要一定时间来调查和核查，完成后可以在收藏馆查看结果。</p>}
        {status && !running && status.job.error && (
          <div className="speech" style={{ textAlign: 'left', color: 'var(--red)', maxHeight: 160, fontSize: 12 }}>
            {status.job.error.slice(-800)}
          </div>
        )}

        <div className="ritual-actions">
          {running ? (
            <button className="btn btn-red" disabled={cancelling} onClick={cancel}>{cancelling ? '取消中…' : '不抽了'}</button>
          ) : status ? (
            <button className="btn btn-ghost" onClick={onReset}>新开一轮</button>
          ) : null}
          {!running && status?.job.run_dir && (
            <a className="btn" href={`#/runs/${status.job.run_dir}`}>看看抽到什么了</a>
          )}
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

/* ---------------- 开包 ---------------- */

function PackOpening({ detail, jobId, failed, onReset }: { detail: DiscoverDetail | null; jobId: string | null; failed: boolean; onReset: () => void }) {
  const cards = useMemo(() => (detail ? sortCards(detail.cards) : []), [detail])
  const [allFlipped, setAllFlipped] = useState(false)
  const [flash, setFlash] = useState(false)

  useEffect(() => {
    if (!allFlipped) return
    if (cards.some((c) => rarityOf(c) === 'SS')) {
      setFlash(true)
      setTimeout(() => setFlash(false), 700)
    }
  }, [allFlipped, cards])

  if (failed) {
    return (
      <div className="pack-stage">
        <h2 className="pixel-big" style={{ color: 'var(--red)', fontSize: 20 }}>✗ 召唤未完成</h2>
        <p className="muted small">召唤没有完成，可以在任务记录中查看具体原因。</p>
        <a className="btn" href="#/collection">去收藏</a>
        <p className="pixel small muted">{jobId}</p>
      </div>
    )
  }

  if (!detail) {
    return <div className="pack-stage"><h2 className="pixel-big" style={{ color: 'var(--gold)', fontSize: 18 }}>正在整理卡片…</h2></div>
  }

  if (cards.length === 0) {
    return (
      <div className="pack-stage" style={{ padding: 30, textAlign: 'center' }}>
        <h2 className="pixel-big" style={{ color: 'var(--gold)', fontSize: 19 }}>本轮没有留下灵感卡</h2>
        <p style={{ maxWidth: 520, lineHeight: 1.8 }}>
          本轮没有留下灵感卡，可以查看报告了解原因。<br />
          <span className="muted small">{detail.run?.stop_reason ?? ''}</span>
        </p>
        <div style={{ display: 'flex', gap: 12 }}>
          <a className="btn" href={`#/runs/${detail.dir}`}>看报告</a>
            <button className="btn btn-ghost" onClick={onReset}>再抽</button>
        </div>
      </div>
    )
  }

  return (
    <div className="pack-stage">
      {flash && <motion.div className="pack-flash" initial={{ opacity: 0.95 }} animate={{ opacity: 0 }} transition={{ duration: 0.7 }} />}
      <motion.h2
        className="pixel-big"
        style={{ color: 'var(--gold)', fontSize: 20, textShadow: '0 4px 0 rgba(0,0,0,.55)' }}
        initial={{ scale: 0.4, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 260, damping: 14 }}
      >
        🎴 开包
      </motion.h2>
      <div style={{ display: 'flex', gap: 22, flexWrap: 'wrap', justifyContent: 'center', maxWidth: 1100 }}>
        {cards.map((card: DiscoveryCard, i: number) => (
          <motion.div
            key={card.idea_id}
            initial={{ y: 260, x: i % 2 ? 120 : -120, rotate: i % 2 ? 18 : -18, opacity: 0 }}
            animate={{ y: 0, x: 0, rotate: 0, opacity: 1 }}
            transition={{ delay: 0.12 * i, type: 'spring', stiffness: 210, damping: 20 }}
          >
            <IdeaCardView card={card} faceDown={!allFlipped} width={158} backGlow />
          </motion.div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
        {!allFlipped && <button className="btn btn-lg" onClick={() => setAllFlipped(true)}>全部翻开</button>}
        {allFlipped && (
          <>
            <a className="btn btn-lg" href={`#/runs/${detail.dir}`}>看完整报告</a>
            <button className="btn btn-ghost btn-lg" onClick={onReset}>再抽</button>
          </>
        )}
      </div>
      <p className="pixel small muted">点击卡背可以逐张翻开，本轮共有 {cards.length} 张灵感卡。</p>
    </div>
  )
}
