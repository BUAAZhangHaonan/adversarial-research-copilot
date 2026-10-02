import { useRef, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import { useElapsed, useJob } from '../hooks'
import StageRunning from '../components/StageRunning'

interface JudgmentPrefill {
  idea_id?: string
  card_id?: string
  card_version?: number
  title?: string
}

const DEFAULT_BUDGET = 20

export default function Judgment() {
  const location = useLocation() as { state?: JudgmentPrefill }
  const prefill = location.state ?? {}
  const [tab, setTab] = useState<'proposal' | 'idea' | 'card'>(
    prefill.card_id ? 'card' : prefill.idea_id ? 'idea' : 'proposal')
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
    (tab === 'proposal' && proposal.trim().length >= 30) ||
    (tab === 'idea' && !!prefill.idea_id) ||
    (tab === 'card' && !!prefill.card_id)

  const submit = async () => {
    if (submitting.current || jobId || !canSubmit) return
    submitting.current = true
    setBusy(true)
    setError('')
    try {
      const params: Record<string, unknown> = { budget_cny: budget }
      if (tab === 'proposal') params.proposal = proposal
      else if (tab === 'idea') params.idea_id = prefill.idea_id
      else {
        params.card_id = prefill.card_id
        if (prefill.card_version) params.card_version = prefill.card_version
      }
      const r = await api.submitJob('debate', params)
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
        title="⚖️ 审判"
        glyph="⚖️"
        status={status}
        elapsed={elapsed}
        jobId={jobId}
        hint="系统会核对方案的主张、证据和可能的反例，并记录需要修订或不宜继续的原因。"
        onCancel={() => api.cancelJob(jobId)}
        error={pollError}
        onReset={() => setSearch({}, { replace: true })}
      />
    )
  }

  return (
    <div className="page page-form stage-debate" style={{ maxWidth: 780 }}>
      <div className="panel" style={{ padding: '26px 28px' }}>
        <h2 className="panel-title" style={{ fontSize: 18 }}>⚖️ 审判</h2>
        <p className="muted small" style={{ marginTop: 0 }}>
          检查方案是否有足够的证据支持，并保留修订意见与反对理由；实际效果仍需要实验检验。
        </p>

        <div className="tab-row">
          <button className={`tab ${tab === 'proposal' ? 'active' : ''}`} onClick={() => setTab('proposal')}>完整提案</button>
          <button className={`tab tab-locked ${tab === 'idea' ? 'active' : ''}`} onClick={() => setTab('idea')}
            disabled={!prefill.idea_id} title="从召唤的卡牌详情里点「直接审判」即可带入">
            带入灵感卡
          </button>
          <button className={`tab tab-locked ${tab === 'card' ? 'active' : ''}`} onClick={() => setTab('card')}
            disabled={!prefill.card_id} title="从试炼产出的研究卡详情里即可带入">
            带入研究卡
          </button>
        </div>

        {tab === 'proposal' && (
          <textarea
            className="textarea mono"
            placeholder={'# 提案\n粘贴需要核查的提案，说明研究目标、相关工作、验证方法和预计开销。'}
            value={proposal}
            onChange={(e) => setProposal(e.target.value)}
            style={{ minHeight: 220 }}
          />
        )}
        {tab === 'idea' && prefill.idea_id && (
          <div className="prefill-box">
            <span className="chip gold">来源灵感</span>
            <div style={{ fontWeight: 600 }}>{prefill.title ?? prefill.idea_id}</div>
            <p className="muted small" style={{ margin: '6px 0 0' }}>系统会结合这张卡的原始想法与核查笔记，检查其中的主张和证据。</p>
          </div>
        )}
        {tab === 'card' && prefill.card_id && (
          <div className="prefill-box">
            <span className="chip gold">来源研究卡</span>
            <div style={{ fontWeight: 600 }}>{prefill.title ?? prefill.card_id}</div>
            <div className="pixel small muted">{prefill.card_id}{prefill.card_version ? ` · v${prefill.card_version}` : ''}</div>
            <p className="muted small" style={{ margin: '6px 0 0' }}>系统会检查所选版本的研究方案，并核对它引用的证据和来源。</p>
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
            {busy ? '正在提交…' : '开始审判'}
          </button>
        </div>
        {error && <div className="error-text pixel" style={{ marginTop: 10 }}>✗ {error}</div>}
      </div>
    </div>
  )
}
