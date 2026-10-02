import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import type { DiscoveryCard, PauseDiagnostics, PauseRecovery, RunDetail as RunDetailT, StageDetail, StageDoc } from '../types'
import {
  DECISION_LABEL, TRIAGE_LABEL, RARITY_ORDER, fmtCNY, fmtDuration, rarityOf, sortCards,
} from '../rarity'
import IdeaCardView from '../components/IdeaCard'
import Modal from '../components/Modal'
import Markdown from '../components/Markdown'
import BudgetBar from '../components/BudgetBar'
import { RunStatusBadge, AssessmentBadge } from '../components/Badge'
import { useJob, useElapsed } from '../hooks'
import { useCountUp } from '../hooks-count'
import TaskFeed from '../components/TaskFeed'
import RitualCircle from '../components/RitualCircle'
import { BudgetDial, DrawDial, ElapsedBlock } from '../components/Dials'
import { stageNarrative } from '../rarity'

export default function RunDetailPage() {
  const { dir = '' } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<RunDetailT | null>(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<DiscoveryCard | null>(null)
  const [viewFile, setViewFile] = useState<string | null>(null)
  const [fileContent, setFileContent] = useState('')
  const detailRequest = useRef(0)
  const fileRequest = useRef(0)

  const reload = useCallback(async () => {
    const request = ++detailRequest.current
    try {
      const d = await api.runDetail(dir)
      if (request === detailRequest.current) { setDetail(d); setError('') }
    } catch (e) {
      if (request === detailRequest.current) setError(String(e))
    }
  }, [dir])
  useEffect(() => {
    setDetail(null)
    setError('')
    setSelected(null)
    setViewFile(null)
    setFileContent('')
    reload()
    return () => { detailRequest.current++; fileRequest.current++ }
  }, [reload])

  // Keep both the run summary and its newly written artifacts current, including
  // the case where the job finishes before its next status poll.
  useEffect(() => {
    if (detail?.run.status !== 'RUNNING') return
    let alive = true
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      await reload()
      if (alive) timer = setTimeout(poll, 5000)
    }
    timer = setTimeout(poll, 5000)
    return () => { alive = false; clearTimeout(timer) }
  }, [detail?.run.status, reload])

  useEffect(() => {
    if (detail?.mode === 'discover') setSelected((old) => old ? detail.cards.find((c) => c.idea_id === old.idea_id) ?? null : null)
  }, [detail])

  const openFile = async (name: string) => {
    const request = ++fileRequest.current
    setViewFile(name)
    setFileContent('')
    try {
      const r = await api.runFile(dir, name)
      if (request === fileRequest.current) setFileContent(r.content)
    } catch (e) {
      if (request === fileRequest.current) setFileContent(`读取失败: ${e}`)
    }
  }

  if (error && !detail) return <div className="page"><div className="panel error-text" role="alert">载入失败：{error}<button className="btn btn-ghost" onClick={reload}>重试</button></div></div>
  if (!detail) return <div className="page"><p className="muted pixel">正在读取研究记录…</p></div>

  const recovery = detail.pause_recovery
  const pauseKind = recovery?.kind ?? null
  const liveJob = detail.run?.status === 'RUNNING'

  return (
    <div className="page">
      {error && <p className="error-text" role="alert">详情暂时无法更新：{error}<button className="btn btn-ghost" onClick={reload}>重试</button></p>}
      {liveJob && <LiveProgress runDir={detail.dir} mode={detail.mode} onDone={reload} />}
      <Hero d={detail} onBack={() => navigate('/collection')} />
      {detail.presentation && <p className="small muted">{detail.presentation.label} · {detail.presentation.revised_at.slice(0, 10)} · 原研究判断与证据限制保留</p>}
      {detail.run.interrupted && (
        <div className="panel panel-notice" role="status" style={{ marginTop: 16 }}>
          任务进程已停止，已有产物保留。ARC 原始检查点状态为 {detail.run.arc_status ?? '未知'}，
          未完成调用的费用与恢复方式仍需检查；本次停止不会自动续跑。
        </div>
      )}

      {detail.pause_diagnostics && <PauseDiagnosticPanel diagnostics={detail.pause_diagnostics} recovery={recovery} />}
      {pauseKind && (
        <ResumePanel
          runId={detail.dir}
          onResumed={reload}
          mode={detail.mode}
          kind={pauseKind}
          actionable={recovery?.actionable ?? true}
          unavailableReason={recovery?.reason}
          onResummon={() => navigate('/summon', { state: { topic: detail.topic } })}
        />
      )}

      {detail.mode === 'discover' && <DiscoverBody d={detail} onSelect={setSelected} onOpenFile={openFile} />}
      {detail.mode !== 'discover' && <StageBody d={detail} onOpenFile={openFile} />}

      {/* ---------- 卡牌详情 ---------- */}
      <Modal
        open={!!selected}
        onClose={() => setSelected(null)}
        wide
        title={selected ? `${rarityOf(selected)} · ${(selected.presentation?.presentation_title || selected.seed?.title)?.slice(0, 40) ?? selected.idea_id}` : ''}
      >
        {selected && <CardDetail card={selected} onClose={() => setSelected(null)} onOpenFile={openFile} navigate={navigate} />}
      </Modal>

      {/* ---------- 原始文件查看 ---------- */}
      <Modal open={!!viewFile} onClose={() => { fileRequest.current++; setViewFile(null) }} wide title={viewFile ?? ''}>
        <div onClick={(e) => e.stopPropagation()}>
          {viewFile?.endsWith('.json') ? (
            <PrettyJson text={fileContent} />
          ) : (
            <div className="speech" style={{ maxHeight: '64vh', overflow: 'auto' }}>
              <Markdown text={fileContent} fileName={viewFile ?? undefined} files={detail.files.map((f) => f.name)} onOpenFile={openFile} />
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}

/* ================= 英雄区 ================= */

function copyText(text: string): Promise<void> {
  // http 局域网访问时 navigator.clipboard 不存在,退回 execCommand
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text)
  return new Promise((resolve, reject) => {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    try {
      document.execCommand('copy') ? resolve() : reject(new Error('copy failed'))
    } finally {
      ta.remove()
    }
  })
}

/** 统计数字滚动:纯数字与 ¥ 金额从 0 滚到位,时间等复杂值原样显示 */
function StatNum({ value }: { value: string }) {
  const m = value.match(/^(¥)?([\d.]+)$/)
  const target = m ? parseFloat(m[2]) : 0
  const n = useCountUp(target)
  if (!m) return <>{value}</>
  const digits = m[2].includes('.') ? m[2].split('.')[1].length : 0
  return <>{m[1]}{n.toFixed(digits)}</>
}

function Hero({ d, onBack }: { d: RunDetailT; onBack: () => void }) {
  const meta = {
    discover: { icon: '🎴', name: '召唤' },
    develop: { icon: '⚔️', name: '试炼' },
    debate: { icon: '⚖️', name: '审判' },
  }[d.mode]
  const titleRef = useRef<HTMLHeadingElement>(null)
  const [expanded, setExpanded] = useState(false)
  const [clamped, setClamped] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const el = titleRef.current
    setClamped(!!el && el.scrollHeight > el.clientHeight + 2)
  }, [d.topic, expanded])

  const onCopy = () => {
    copyText(d.topic || '').then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }).catch(() => {})
  }


  const stats: { label: string; value: string; hint?: string }[] = []
  if (d.mode === 'discover') {
    const dd = d as Extract<RunDetailT, { mode: 'discover' }>
    const lead = dd.cards.filter((c) => c.note?.decision === 'lead').length
    stats.push(
      { label: '灵感', value: String(dd.cards.length), hint: '本轮抽出的卡' },
      ...(lead ? [{ label: '线索', value: String(lead), hint: '有条件线索，仍需证据核查' }] : []),
    )
  } else {
    const sd = d as StageDetail
    stats.push({ label: '文档', value: String((sd.docs ?? []).length), hint: '研究卡与技术报告' })
  }
  if (d.run?.created_at) {
    stats.push({ label: '用时', value: fmtDuration(d.run.created_at, d.run.updated_at), hint: '从任务开始到结束' })
  }
  if (d.cost?.spent_upper_cny != null) {
    stats.push({ label: '花费', value: fmtCNY(d.cost.spent_upper_cny, 2), hint: `上限 ${fmtCNY(d.cost.limit_cny, 0)}` })
  }

  return (
    <div className={`panel hero ${d.mode === 'debate' ? 'hero-debate' : d.mode === 'develop' ? 'hero-develop' : 'hero-discover'}`}>
      <div className="hero-top">
        <span className="hero-icon">{meta.icon}</span>
        <div className="hero-title-wrap">
          <div className="hero-mode pixel">{meta.name} · {d.mode === 'debate' ? 'PRESSURE TEST' : d.mode.toUpperCase()}</div>
          <h1 ref={titleRef} className={`hero-title ${expanded ? 'hero-title-open' : ''}`}>{d.topic || '未命名'}</h1>
          <div className="hero-tools">
            {(clamped || expanded) && (
              <button className="hero-tool" onClick={() => setExpanded(!expanded)}>
                {expanded ? '▴ 收起' : '▾ 展开全文'}
              </button>
            )}
            <button className="hero-tool" onClick={onCopy} title="复制原始问题全文">
              {copied ? '✓ 已复制' : '⧉ 复制'}
            </button>
          </div>
        </div>
        <button className="btn btn-ghost hero-back" onClick={onBack}>← 收藏馆</button>
      </div>
      <div className="hero-meta">
        <RunStatusBadge status={d.run?.status} stopReason={d.run?.stop_reason} />
        <AssessmentBadge assessment={d.run?.assessment} />
        <span style={{ flex: 1 }} />
        {stats.map((s) => (
          <div key={s.label} className="stat" title={s.hint}>
            <span className="stat-value num"><StatNum value={s.value} /></span>
            <span className="stat-label pixel">{s.label}</span>
          </div>
        ))}
      </div>
      {d.cost && d.cost.limit_cny && <BudgetBar cost={d.cost} compact />}
    </div>
  )
}

/* ================= 预算续跑 ================= */

/* ================= 进行中实时进度（从大厅「去看」进来的落点） ================= */

function LiveProgress({ runDir, mode, onDone }: { runDir: string; mode: string; onDone: () => void }) {
  const [jobId, setJobId] = useState<string | null>(null)
  const [unsettled, setUnsettled] = useState(true)
  const { status, error: pollError } = useJob(jobId)
  const elapsed = useElapsed(status?.job.created_at, status?.job.finished_at)
  const [showLog, setShowLog] = useState(false)
  const notified = useRef<string | null>(null)
  const [scanError, setScanError] = useState('')
  const [cancelError, setCancelError] = useState('')
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout>
    setJobId(null)
    notified.current = null
    const scan = async () => {
      try {
        const r = await api.jobs()
        if (!alive) return
        const matching = r.jobs.filter((x) => x.run_dir === runDir)
        const j = matching.find((x) => x.status === 'running') ?? matching[0]
        // Retain a known job until its terminal status has been observed.
        if (j) setJobId(j.id)
        setUnsettled(j?.status === 'running')
        setScanError('')
      } catch (e) { if (alive) setScanError(String(e)) }
      finally { if (alive) timer = setTimeout(scan, 5000) }
    }
    scan()
    return () => { alive = false; clearTimeout(timer) }
  }, [runDir])

  useEffect(() => {
    if (status && jobId && status.job.status !== 'running' && notified.current !== jobId) {
      notified.current = jobId
      onDone()
    }
  }, [status, jobId, onDone])

  if (!jobId) return <p className={scanError ? 'error-text' : 'muted'}>{scanError ? `任务状态暂时无法更新：${scanError}` : '正在同步任务状态…'}</p>
  const p = status?.progress
  const running = status?.job.status === 'running'
  const meta = { discover: '召唤', develop: '试炼', debate: '审判' }[mode] ?? '任务'
  const glyph = mode === 'discover' ? '🔮' : mode === 'develop' ? '⚔️' : '⚖️'
  const draws = p?.draws

  return (
    <div className="panel ritual-stage" style={{ marginTop: 18 }}>
      <h2 className={`pixel-big ritual-title ${running ? 'rt-running' : 'rt-paused'}`}>
        {running ? `${meta}进行中` : `${meta}已结束`}
      </h2>
      <p className="ritual-narrative">{stageNarrative(p?.current, mode)}</p>
      {(pollError || scanError || cancelError) && <p className="error-text" role="alert">{cancelError ? `终止失败：${cancelError}` : `状态暂时无法更新：${pollError || scanError}`}</p>}

      <div className="ritual-deck">
        {mode === 'discover' ? (
          <DrawDial started={draws?.started ?? 0} max={draws?.max ?? 0} active={running} />
        ) : (
          <DrawDial started={p?.rounds_completed ?? 0} max={0} active={running} />
        )}
        <RitualCircle size={168} state={running ? 'running' : 'done'} core={glyph} />
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

      <div className="ritual-actions">
        {running && (
          <button className="btn btn-red" disabled={cancelling} onClick={async () => {
            setCancelling(true)
            setCancelError('')
            try { await api.cancelJob(jobId); await onDone() }
            catch (e) { setCancelError(String(e)) }
            finally { setCancelling(false) }
          }}>{cancelling ? '终止中…' : '终止'}</button>
        )}
        <button className="btn btn-ghost" onClick={() => setShowLog(!showLog)}>
          {showLog ? '收起日志' : '日志'}
        </button>
        {unsettled && <span className="pixel small muted">跑完自动出结果</span>}
      </div>
      {showLog && (
        <div className="speech mono" style={{ marginTop: 14, textAlign: 'left', maxHeight: 260, fontSize: 12 }}>
          {status?.log_tail || '(还没有输出)'}
        </div>
      )}
    </div>
  )
}

function PauseDiagnosticPanel({ diagnostics: d, recovery }: { diagnostics: PauseDiagnostics; recovery?: PauseRecovery | null }) {
  const route = recovery?.action === 'retry-task' ? '重新执行暂停的步骤'
    : recovery?.action === 'defer-evidence' ? '根据现有材料重新整理结论'
    : recovery?.kind === 'evidence' ? '根据现有材料整理结论，再继续其余候选'
    : recovery?.kind === 'budget' ? '追加预算后继续' : '从检查点继续'
  return (
    <div className="panel panel-notice" style={{ marginTop: 12 }}>
      <h3 className="panel-title">暂停诊断</h3>
      <p className="small">任务：<code style={{ overflowWrap: 'anywhere' }}>{d.task_id || '尚未定位'}</code></p>
      {d.stop_reason && <p className="small">暂停原因：<code>{d.stop_reason}</code></p>}
      {d.recovery_error && <pre className="error-text small" role="alert" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>上次恢复失败：{d.recovery_error}</pre>}
      {d.errors.length > 0 && <ul className="small">{d.errors.map((error, i) => <li key={i} style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{error}</li>)}</ul>}
      {d.evidence_requests.length > 0 && <>
        <p className="small">仍待核查的证据：</p>
        <ul className="small">{d.evidence_requests.map((request, i) => <li key={i}>{request.question}</li>)}</ul>
      </>}
      {d.truncated && <p className="small muted">这里显示了部分诊断信息，完整记录仍保留在相关文件中。</p>}
      {recovery && <p className="small">恢复方式：{recovery.actionable ? route : recovery.reason || '需要人工检查'}</p>}
    </div>
  )
}

function ResumePanel({ runId, onResumed, mode, kind, actionable = true, unavailableReason, onResummon }: {
  runId: string
  onResumed: () => void
  mode: string
  kind: PauseRecovery['kind']
  actionable?: boolean
  unavailableReason?: string | null
  onResummon: () => void
}) {
  const [extra, setExtra] = useState(10)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [resumeJob, setResumeJob] = useState<string | null>(null)
  const submitting = useRef(false)
  const { status, error: pollError } = useJob(resumeJob)

  useEffect(() => {
    if (status && status.job.status !== 'running' && resumeJob) {
      if (status.job.status === 'failed') setError(status.job.error || '恢复命令失败，请查看暂停诊断。')
      onResumed()
      setResumeJob(null)
    }
  }, [status, resumeJob, onResumed])

  const resume = async () => {
    if (submitting.current || resumeJob) return
    submitting.current = true
    setBusy(true)
    setError('')
    try {
      const r = await api.submitJob('resume', kind === 'budget' ? { run_id: runId, add_budget_cny: extra } : { run_id: runId })
      setResumeJob(r.job_id)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '提交失败')
    } finally {
      setBusy(false)
      submitting.current = false
    }
  }

  const copy = {
    budget: {
      title: '预算已用尽，任务暂停',
      body: '已有结果和费用记录会保留，你可以设置追加预算，从暂停的步骤继续。',
      btn: '继续',
    },
    retry: {
      title: '当前步骤的输出格式需要修复',
      body: '当前步骤的输出未通过格式检查，任务已暂停。重试将保留已经完成的结果和费用记录。',
      btn: '重试这一步',
    },
    defer: {
      title: actionable
        ? '关键文献暂时无法获取'
        : '关键材料仍待核查',
      body: actionable
        ? '关键文献暂时无法获取，相关判断还不能确认。你可以选择按现有材料继续，缺失的证据会保留在限制说明中。'
        : unavailableReason || '现有草稿不满足证据延期条件，需要检查材料和恢复方式。已有产物保留。',
      btn: '按现有材料继续',
    },
    evidence: {
      title: '材料受限，可继续完成本轮',
      body: '继续后，这一步会利用已取得的材料补写有限结论。若仍无法形成合格结果，将保留待查并继续其余抽取。缺失证据继续记为限制，已有草稿不会直接当作通过。',
      btn: '按现有材料继续',
    },
    resume: {
      title: '可从检查点继续',
      body: unavailableReason || '已有工作和账目保留，可从检查点继续。若外部条件仍未满足，任务会保留新的暂停原因。',
      btn: '继续',
    },
  }[kind]

  return (
    <div className="panel panel-notice" style={{ marginTop: 12 }}>
      <h3 className="panel-title">{copy.title}</h3>
      <p className="small" style={{ marginTop: 0 }}>{copy.body}</p>
      {!actionable && (
        <div style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap' }}>
          <button className="btn" onClick={onResummon}>🔮 同题重抽一轮</button>
          {mode === 'discover' && (
            <span className="pixel small muted" style={{ alignSelf: 'center' }}>已有灵感卡仍可以送入试炼。</span>
          )}
        </div>
      )}
      {actionable && (
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        {kind === 'budget' && (
          <label className="pixel small" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            追加
            <input className="input pixel" type="number" min={1} max={200} style={{ width: 90 }}
              value={extra} onChange={(e) => setExtra(Math.max(1, Math.min(200, Number(e.target.value) || 10)))} />
            元
          </label>
        )}
        <button className="btn" disabled={busy || !!resumeJob} onClick={resume}>
          {resumeJob ? '续跑中…' : copy.btn}
        </button>
        {resumeJob && status?.progress?.budget && <span className="chip">{fmtCNY(status.progress.budget.spent_upper_cny)} 已知费用</span>}
      </div>
      )}
      {error && <div className="error-text pixel" style={{ marginTop: 8 }}>✗ {error}</div>}
      {pollError && <p className="error-text" role="alert">续跑状态暂时无法更新：{pollError}，正在重试。</p>}
    </div>
  )
}

/* ================= DISCOVER ================= */

function DiscoverBody({ d, onSelect, onOpenFile }: {
  d: Extract<RunDetailT, { mode: 'discover' }>
  onSelect: (c: DiscoveryCard) => void
  onOpenFile: (n: string) => void
}) {
  const sorted = useMemo(() => sortCards(d.cards), [d.cards])
  const counts = sorted.reduce<Record<string, number>>((acc, c) => {
    const r = rarityOf(c)
    acc[r] = (acc[r] ?? 0) + 1
    return acc
  }, {})

  return (
    <>
      {d.files.some((f) => f.name === 'REPORT.md') && (
        <div className="panel" style={{ marginTop: 14 }}>
          <div className="section-head" style={{ marginTop: 0 }}>
            <h2 className="section-title">本次研究发现</h2>
            <button className="btn btn-ghost" onClick={() => onOpenFile('REPORT.md')}>查看完整报告</button>
          </div>
          <ReportView dir={d.dir} revision={d.presentation?.revised_at ?? d.run.updated_at} files={d.files.map((f) => f.name)} onOpenFile={onOpenFile} />
        </div>
      )}
      <div className="section-head">
        <h2 className="section-title">灵感卡</h2>
        <span className="section-hint">打开感兴趣的卡片，了解详情后再决定是否继续。</span>
        <span style={{ flex: 1 }} />
        <span className="section-sub pixel">
          {(['SS', 'S', 'A', 'B', 'X'] as const)
            .filter((r) => counts[r])
            .sort((a, b) => RARITY_ORDER[a] - RARITY_ORDER[b])
            .map((r) => `${r}×${counts[r]}`)
            .join(' · ')}
        </span>
      </div>
      <div className="card-wall">
        {sorted.map((c, i) => (
          <motion.div
            key={c.idea_id}
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: Math.min(i * 0.06, 0.5), duration: 0.35, ease: 'easeOut' }}
          >
            <IdeaCardView card={c} onClick={onSelect} />
          </motion.div>
        ))}
        {sorted.length === 0 && <p className="muted">这一轮没有留下卡。</p>}
      </div>
      <DocShelf d={d} onOpen={onOpenFile} />
    </>
  )
}

/* ================= DEVELOP / DEBATE ================= */

const DOC_LABEL: Record<StageDoc['kind'], (doc: StageDoc) => string> = {
  card: (doc) => `研究卡 v${doc.version}`,
  idea: () => '灵感卡',
  technical: () => '技术报告',
}

function StageBody({ d, onOpenFile }: { d: StageDetail; onOpenFile: (n: string) => void }) {
  const navigate = useNavigate()
  const report = d.files.find((f) => f.name === 'REPORT.md')
  const [activeDoc, setActiveDoc] = useState<string | null>(null)
  const [docContent, setDocContent] = useState('')
  const selectedDoc = d.docs.find((doc) => doc.file === activeDoc)

  useEffect(() => { setActiveDoc(null) }, [d.dir])

  useEffect(() => {
    if (!activeDoc) return
    let alive = true
    setDocContent('')
    api.runFile(d.dir, activeDoc).then((r) => { if (alive) setDocContent(r.content) }).catch((e) => { if (alive) setDocContent(`读取失败：${e}`) })
    return () => { alive = false }
  }, [activeDoc, d.dir, d.run.updated_at, selectedDoc?.size])

  const inputIdea = d.input_idea as { seed?: { title?: string }; idea_id?: string } | null

  return (
    <>
      {inputIdea?.seed?.title && (
        <div className="origin-strip">
          <span className="chip gold">来自灵感</span>
          <span className="origin-title">{inputIdea.seed.title}</span>
        </div>
      )}

      {report && (
        <div className="panel" style={{ marginTop: 14 }}>
          <div className="section-head" style={{ marginTop: 0 }}>
            <h2 className="section-title">{d.mode === 'develop' ? '这一轮发生了什么' : '核查结论'}</h2>
            <button className="btn btn-ghost" style={{ padding: '4px 12px', fontSize: 12 }} onClick={() => onOpenFile('REPORT.md')}>
              查看完整报告
            </button>
          </div>
          <ReportView dir={d.dir} revision={d.presentation?.revised_at ?? d.run.updated_at} files={d.files.map((f) => f.name)} onOpenFile={onOpenFile} />
        </div>
      )}

      {(d.docs ?? []).length > 0 && (
        <div className="panel" style={{ marginTop: 14 }}>
          <div className="section-head" style={{ marginTop: 0 }}>
            <h2 className="section-title">{d.mode === 'develop' ? '研究方案卡' : '本轮研究卡与文档'}</h2>
          </div>
          <div className="tab-row">
            {(d.docs ?? []).map((doc) => (
              <button
                key={doc.file}
                className={`tab ${activeDoc === doc.file ? 'active' : ''}`}
                onClick={() => setActiveDoc(activeDoc === doc.file ? null : doc.file)}
              >
                {DOC_LABEL[doc.kind](doc)}
              </button>
            ))}
          </div>
          {activeDoc && (
            <div className="speech md-body" style={{ maxHeight: '56vh', overflow: 'auto', marginTop: 12 }}>
              {docContent ? <Markdown text={docContent} fileName={activeDoc} files={d.files.map((f) => f.name)} onOpenFile={onOpenFile} /> : <p className="muted small">正在读取内容…</p>}
            </div>
          )}
          {!activeDoc && <p className="muted small" style={{ marginBottom: 0 }}>选择一版研究卡即可查看全文，版本号最大的卡片是最新记录。</p>}
          {selectedDoc?.kind === 'card' && selectedDoc.card_id && (
            <button className="btn" style={{ marginTop: 12 }} onClick={() => navigate('/judgment', { state: { card_id: selectedDoc.card_id, card_version: selectedDoc.version, title: d.topic } })}>⚖️ 带入这版研究卡审判</button>
          )}
        </div>
      )}

      <DocShelf d={d} onOpen={onOpenFile} />
    </>
  )
}

function ReportView({ dir, revision, files, onOpenFile }: { dir: string; revision: string | null; files: string[]; onOpenFile: (name: string) => void }) {
  const [content, setContent] = useState('')
  useEffect(() => {
    let alive = true
    setContent('')
    api.runFile(dir, 'REPORT.md').then((r) => { if (alive) setContent(r.content) }).catch((e) => { if (alive) setContent(`读取失败：${e}`) })
    return () => { alive = false }
  }, [dir, revision])
  if (!content) return <p className="muted small">正在读取内容…</p>
  return (
    <div className="speech md-body" style={{ maxHeight: '64vh', overflow: 'auto', marginTop: 4 }}>
      <Markdown text={content} fileName="REPORT.md" files={files} onOpenFile={onOpenFile} />
    </div>
  )
}

/* ================= 档案(精选入口 + 折叠抽屉) ================= */

const FEATURED: { match: (n: string) => boolean; icon: string; label: string }[] = [
  { match: (n) => n === 'WRITING_REVISION.md', icon: '✎', label: '本次文字更新' },
  { match: (n) => n === 'FIELD_BRIEF.md', icon: '📚', label: '领域简报' },
  { match: (n) => n === 'TECHNICAL_REPORT.md', icon: '🔬', label: '技术报告' },
  { match: (n) => n === 'SEARCH_SOURCES.md', icon: '🔍', label: '检索来源' },
  { match: (n) => n === 'COST_REPORT.md', icon: '🧾', label: '费用明细' },
]

function DocShelf({ d, onOpen }: { d: RunDetailT; onOpen: (n: string) => void }) {
  const [open, setOpen] = useState(false)
  const all = d.files.map((f) => f.name)
  const featured = FEATURED
    .map((f) => ({ ...f, name: all.find(f.match) }))
    .filter((f): f is typeof f & { name: string } => !!f.name)
  const rest = d.files.filter((f) => !featured.some((x) => x.name === f.name))
  if (!featured.length && !rest.length) return null

  return (
    <div className="doc-shelf">
      {featured.map((f) => (
        <button key={f.name} className="doc-card shine" onClick={() => onOpen(f.name)}>
          <span className="doc-icon">{f.icon}</span>
          <span className="doc-label pixel">{f.label}</span>
        </button>
      ))}
      {rest.length > 0 && (
        <>
          <button className="doc-card doc-more" onClick={() => setOpen(!open)}>
            <span className="doc-icon">{open ? '▾' : '▸'}</span>
            <span className="doc-label pixel">档案 {rest.length}</span>
          </button>
          {open && (
            <div className="doc-drawer">
              {rest.map((f) => (
                <button key={f.name} className="btn btn-ghost" style={{ padding: '4px 12px', fontSize: 11 }} onClick={() => onOpen(f.name)}>
                  {f.name}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

/* ================= 卡牌详情 ================= */

function CardDetail({ card, onClose, onOpenFile, navigate }: {
  card: DiscoveryCard
  onClose: () => void
  onOpenFile: (n: string) => void
  navigate: ReturnType<typeof useNavigate>
}) {
  return (
    <div style={{ display: 'flex', gap: 22, flexWrap: 'wrap' }} onClick={(e) => e.stopPropagation()}>
      <div><IdeaCardView card={card} width={190} /></div>
      <div style={{ flex: 1, minWidth: 300, display: 'grid', gap: 10 }}>
        {card.presentation && (
          <Field label={`当前判断 · ${DECISION_LABEL[card.note?.decision ?? ''] ?? TRIAGE_LABEL[card.triage?.action ?? ''] ?? card.status}`}>
            <Markdown text={card.presentation.text} />
            {!!card.note?.limits?.length && <div className="small"><strong>证据限制</strong><ul>{card.note.limits.map((limit, i) => <li key={i}>{limit}</li>)}</ul></div>}
          </Field>
        )}
        <details open={card.presentation ? undefined : true}>
        {card.presentation && <summary className="muted small" style={{ cursor: 'pointer' }}>查看原始研究字段</summary>}
        {card.seed && (
          <>
            <Field label="问题">{card.seed.question}</Field>
            <Field label="核心想法">{card.seed.insight}</Field>
            <Field label="为什么值得做">{card.seed.why_it_matters}</Field>
            <Field label="跟已知工作的差别">{card.seed.difference_from_known}</Field>
            <Field label="尚待确认的问题">{card.seed.key_unknown}</Field>
          </>
        )}
        {card.triage && (
          <Field label={`初步评估 · ${card.triage.action === 'investigate' ? '入围' : card.triage.action === 'park' ? '搁置' : '放弃'}`}>
            <Markdown text={card.triage.reason} />
            <div className="muted small" style={{ marginTop: 4 }}>主要反对理由：{card.triage.strongest_objection}</div>
          </Field>
        )}
        {card.note && (
          <Field label={`预研 · ${DECISION_LABEL[card.note.decision] ?? card.note.decision}`}>
            <Markdown text={card.note.reason} />
            <div className="note-grid">
              <span className="muted">可行性</span><span>{card.note.feasibility}</span>
              <span className="muted">主要风险</span><span>{card.note.main_risk}</span>
              <span className="muted">需要确认的问题</span><span>{card.note.next_question}</span>
              <span className="muted">算力</span>
              <span>{card.note.resources?.gpu_type ?? '—'}{card.note.resources?.gpu_count ? ` × ${card.note.resources.gpu_count}` : ''}</span>
            </div>
            {!!card.note.limits?.length && <div className="small" style={{ marginTop: 8 }}><strong>证据限制</strong><ul>{card.note.limits.map((limit, i) => <li key={i}>{limit}</li>)}</ul></div>}
            {!!card.note.nearest_work?.length && (
              <div style={{ marginTop: 8 }}>
                <div className="pixel" style={{ fontSize: 11, color: 'var(--gold)' }}>最相关的已有工作</div>
                {card.note.nearest_work.slice(0, 3).map((w, i) => (
                  <div key={i} className="small nearest-work">
                    <div>相关工作的结果：{w.already_established}</div>
                    <div style={{ color: 'var(--blue)' }}>与当前想法的差别：{w.remaining_difference}</div>
                    {w.uncertainty && <div className="muted">未确认：{w.uncertainty}</div>}
                    <div className="muted">来源：{w.source_id}</div>
                  </div>
                ))}
              </div>
            )}
          </Field>
        )}
        {!card.note && <div className="muted small">{card.triage?.action === 'park' || card.triage?.action === 'drop' ? '初步评估后，这个想法没有继续进入核查。' : '尚无定向预研结论，可能仍在处理或暂停。'}</div>}
        </details>
        <div className="card-actions">
          <button className="btn btn-blue" onClick={() => navigate('/trial', { state: { idea_id: card.idea_id, title: card.presentation?.presentation_title || card.seed?.title } })}>
            ⚔️ 送入试炼
          </button>
          <button className="btn" onClick={() => navigate('/judgment', { state: { idea_id: card.idea_id, title: card.presentation?.presentation_title || card.seed?.title } })}>
            ⚖️ 直接审判
          </button>
          {card.idea_md && (
            <button className="btn btn-ghost" onClick={() => { onClose(); onOpenFile(card.idea_md!) }}>📄 全文</button>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="pixel field-label">{label}</div>
      <div className="field-body">{children}</div>
    </div>
  )
}

function PrettyJson({ text }: { text: string }) {
  let pretty = text
  try {
    pretty = JSON.stringify(JSON.parse(text), null, 2)
  } catch { /* keep raw */ }
  return <pre className="speech mono" style={{ maxHeight: '64vh', fontSize: 12 }}>{pretty}</pre>
}
