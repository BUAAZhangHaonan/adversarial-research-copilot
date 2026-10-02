import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { RunSummary } from '../types'
import { MODE_LABEL, fmtCNY, fmtRelative } from '../rarity'
import { RunStatusBadge, AssessmentBadge } from '../components/Badge'

export default function Collection() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [filter, setFilter] = useState<'all' | 'discover' | 'develop' | 'debate'>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        const r = await api.runs()
        if (alive) { setRuns(r.runs); setError('') }
      } catch (e) { if (alive) setError(String(e)) }
      finally {
        if (alive) { setLoading(false); timer = setTimeout(poll, 5000) }
      }
    }
    poll()
    return () => { alive = false; clearTimeout(timer) }
  }, [])

  const shown = runs.filter((r) => filter === 'all' || r.mode === filter)

  return (
    <div className="page">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 18, flexWrap: 'wrap' }}>
        <h2 className="section-title" style={{ margin: 0 }}>🗄 收藏馆</h2>
        <span style={{ flex: 1 }} />
        {(['all', 'discover', 'develop', 'debate'] as const).map((f) => (
          <button key={f} className={`btn ${filter === f ? '' : 'btn-ghost'}`} style={{ padding: '5px 14px', fontSize: 12 }}
            onClick={() => setFilter(f)}>
            {f === 'all' ? '全部' : MODE_LABEL[f]}
          </button>
        ))}
      </div>

      {loading && <p className="muted">正在读取研究记录…</p>}
      {error && <p className="error-text" role="alert">收藏暂时无法更新：{error}，正在重试。</p>}
      {!loading && !error && shown.length === 0 && (
        <div className="empty-state">
          <div className="empty-card-back">♠</div>
          <p>{filter === 'all' ? '收藏馆还没有研究记录，可以从召唤开始。' : '这个分类暂无记录。'}</p>
          <a className="btn" href="#/summon">去召唤</a>
        </div>
      )}

      <div style={{ display: 'grid', gap: 13, marginTop: 14 }}>
        {shown.map((r) => (
          <div key={r.dir} className={`panel run-row acc-${r.mode}`} role="link" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/runs/${r.dir}`) }} onClick={() => navigate(`/runs/${r.dir}`)}>
            <span className="run-icon">{modeIcon(r.mode)}</span>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <RunStatusBadge status={r.status} stopReason={r.stop_reason} />
                <AssessmentBadge assessment={r.assessment} />
              </div>
              <div className="run-topic" title={r.topic}>{r.topic || '(没有主题)'}</div>
            </div>
            <div className="run-side">
              <div className="pixel small num" title="花费上界">{fmtCNY(r.cost?.spent_upper_cny ?? null, 2)}</div>
              <div className="pixel small muted">{fmtRelative(r.created_at)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function modeIcon(mode: string) {
  return { discover: '🎴', develop: '⚔️', debate: '⚖️' }[mode] ?? '📄'
}
