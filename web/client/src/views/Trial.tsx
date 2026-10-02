import { useRef, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import { useElapsed, useJob } from '../hooks'
import StageRunning from '../components/StageRunning'

interface TrialPrefill { idea_id?: string; title?: string }

const DEFAULT_BUDGET = 20

export default function Trial() {
  const location = useLocation() as { state?: TrialPrefill }
  const prefill = location.state ?? {}
  const [tab, setTab] = useState<'question' | 'proposal' | 'idea'>(prefill.idea_id ? 'idea' : 'question')
  const [question, setQuestion] = useState('')
  const [proposal, setProposal] = useState('')
  const [budget, setBudget] = useState(DEFAULT_BUDGET)
  const [search, setSearch] = useSearchParams()
  const jobId = search.get('job')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submitting = useRef(false)
  const { status, error: pollError } = useJob(jobId)
  const elapsed = useElapsed(status?.job.created_at, status?.job.finished_at)

  const canSubmit =
    (tab === 'question' && question.trim().length >= 15) ||
    (tab === 'proposal' && proposal.trim().length >= 30) ||
    (tab === 'idea' && !!prefill.idea_id)

  const submit = async () => {
    if (submitting.current || jobId || !canSubmit) return
    submitting.current = true
    setBusy(true)
    setError('')
    try {
      const params: Record<string, unknown> = { budget_cny: budget }
      if (tab === 'question') params.question = question
      else if (tab === 'proposal') params.proposal = proposal
      else params.idea_id = prefill.idea_id
      const r = await api.submitJob('develop', params)
      setSearch({ job: r.job_id }, { replace: true })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '提交失败')
    } finally {
      setBusy(false)
      submitting.current = false
    }
  }

  if (jobId) {
    return (
      <StageRunning
        title="⚔️ 试炼"
        glyph="⚔️"
        status={status}
        elapsed={elapsed}
        jobId={jobId}
        hint="系统会查阅相关工作并展开研究方案，完成后会将结果保存在收藏馆。"
        onCancel={() => api.cancelJob(jobId)}
        error={pollError}
        onReset={() => setSearch({}, { replace: true })}
      />
    )
  }

  return (
    <div className="page page-form stage-develop" style={{ maxWidth: 780 }}>
      <div className="panel" style={{ padding: '26px 28px' }}>
        <h2 className="panel-title" style={{ fontSize: 18 }}>⚔️ 试炼</h2>
        <p className="muted small" style={{ marginTop: 0 }}>
          输入一个问题或选择已有灵感，把它展开为研究方案，并查看实施条件和证据限制。
        </p>

        <div className="tab-row">
          <button className={`tab ${tab === 'question' ? 'active' : ''}`} onClick={() => setTab('question')}>一句话问题</button>
          <button className={`tab ${tab === 'proposal' ? 'active' : ''}`} onClick={() => setTab('proposal')}>完整提案</button>
          <button className={`tab tab-locked ${tab === 'idea' ? 'active' : ''}`} onClick={() => setTab('idea')}
            disabled={!prefill.idea_id} title="从召唤的卡牌详情里点「送入试炼」即可带入">
            🔒 带入灵感卡
          </button>
        </div>

        {tab === 'question' && (
          <textarea
            className="textarea"
            placeholder="一句话说清你要研究什么。&#10;例：长推理模型的停止信号，能不能从它自己的表征里读出来？"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            style={{ minHeight: 148 }}
          />
        )}
        {tab === 'proposal' && (
          <textarea
            className="textarea mono"
            placeholder={'# 提案\n粘贴完整提案（markdown）。请说明研究目标、与已有工作的差别、验证方法和预计开销。'}
            value={proposal}
            onChange={(e) => setProposal(e.target.value)}
            style={{ minHeight: 208 }}
          />
        )}
        {tab === 'idea' && prefill.idea_id && (
          <div className="prefill-box">
            <span className="chip gold">来源灵感</span>
            <div style={{ fontWeight: 600 }}>{prefill.title ?? prefill.idea_id}</div>
            <p className="muted small" style={{ margin: '6px 0 0' }}>
              系统会结合这张卡的原始想法、核查笔记和相关资料，继续展开研究方案。
            </p>
          </div>
        )}

        <div style={{ display: 'flex', gap: 12, marginTop: 14, alignItems: 'center', flexWrap: 'wrap' }}>
          <label className="pixel small" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            预算
            <input
              className="input pixel" type="number" min={1} max={200} step={1}
              style={{ width: 90 }} value={budget}
              onChange={(e) => setBudget(Math.max(1, Math.min(200, Number(e.target.value) || DEFAULT_BUDGET)))}
            />
            元
          </label>
          <span style={{ flex: 1 }} />
          <button className="btn btn-lg" disabled={busy || !canSubmit} onClick={submit}>
            {busy ? '正在提交…' : '开始试炼'}
          </button>
        </div>
        {error && <div className="error-text pixel" style={{ marginTop: 10 }}>✗ {error}</div>}
      </div>
    </div>
  )
}
