import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { Health, JobListItem } from '../types'
import { MODE_LABEL, fmtDuration } from '../rarity'

const MODE_CARD: Record<string, { icon: string; title: string; sub: string; to: string; grad: string; first?: boolean }> = {
  discover: {
    icon: '🔮', title: '召唤', to: '/summon', first: true,
    sub: '从你关心的领域出发，寻找值得研究的问题，并核查有潜力的想法。',
    grad: 'linear-gradient(155deg, #37304f, #252338)',
  },
  develop: {
    icon: '⚔️', title: '试炼', to: '/trial',
    sub: '选择一个想法，把研究问题、相关工作和验证方法展开成可以评估的方案。',
    grad: 'linear-gradient(155deg, #293d55, #202839)',
  },
  debate: {
    icon: '⚖️', title: '审判', to: '/judgment',
    sub: '检查方案的主张与证据，保留修订意见和反对理由，供你判断是否继续。',
    grad: 'linear-gradient(155deg, #47363c, #2d2732)',
  },
}

export default function Hall({ health }: { health: Health | null }) {
  const [jobs, setJobs] = useState<JobListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        const r = await api.jobs()
        if (alive) { setJobs(r.jobs); setError('') }
      } catch (e) { if (alive) setError(String(e)) }
      finally {
        if (alive) { setLoading(false); timer = setTimeout(poll, 5000) }
      }
    }
    poll()
    return () => { alive = false; clearTimeout(timer) }
  }, [])

  const running = jobs.filter((j) => j.status === 'running')
  const recent = jobs.filter((j) => j.status !== 'running').slice(0, 5)

  return (
    <div className="page">
      <div className="hall-head">
        <h1 className="hall-title pixel-big">今晚研究点什么？</h1>
        <p className="muted small">从召唤中寻找灵感，再通过试炼展开方案，或送入审判检查它是否站得住。</p>
      </div>

      {loading && <p className="muted">正在读取任务…</p>}
      {error && <p className="error-text" role="alert">任务列表暂时无法更新：{error}，正在重试。</p>}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20, marginTop: 6 }}>
        {Object.entries(MODE_CARD).map(([mode, m]) => (
          <Link key={mode} to={m.to} style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="panel mode-card shine" style={{ background: m.grad }}>
              {m.first && <span className="chip gold first-badge">从这里开始</span>}
              <div style={{ fontSize: 46, marginBottom: 8 }}>{m.icon}</div>
              <h2 className="pixel-big" style={{ color: 'var(--gold)', fontSize: 17, margin: '0 0 10px', textShadow: '0 3px 0 rgba(0,0,0,.5)' }}>
                {m.title}
              </h2>
              <p style={{ fontSize: 13.5, lineHeight: 1.7, color: 'var(--cream)', opacity: 0.92 }}>{m.sub}</p>
              <span className="mode-enter pixel">进入 →</span>
            </div>
          </Link>
        ))}
      </div>

      {running.length > 0 && (
        <div className="panel" style={{ marginTop: 22 }}>
          <h3 className="panel-title">进行中的任务</h3>
          {running.map((j) => (
            <div key={j.id} style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '6px 0' }}>
              <span className="chip warn chip-pulse"><span className="dot-live" />{MODE_LABEL[j.mode] ?? j.mode}</span>
              <span className="small">{jobTitle(j)}</span>
              <span className="spacer" style={{ flex: 1 }} />
              <span className="pixel small muted">{fmtDuration(j.created_at)}</span>
              <Link className="btn btn-ghost" style={{ padding: '4px 12px', fontSize: 12 }} to={jobPath(j)}>查看进度</Link>
            </div>
          ))}
        </div>
      )}

      {recent.length > 0 && (
        <div className="panel" style={{ marginTop: 22 }}>
          <h3 className="panel-title">最近完成的任务</h3>
          {recent.map((j) => (
            <div key={j.id} style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '6px 0', borderBottom: '1px dashed rgba(244,238,216,.12)' }}>
              <span className={`chip ${j.status === 'completed' ? 'ok' : j.status === 'failed' ? 'bad' : 'warn'}`}>
                {statusLabel(j.status)}
              </span>
              <span className="small" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {jobTitle(j)}
              </span>
              <span className="pixel small muted">{MODE_LABEL[j.mode] ?? j.mode}</span>
              <Link className="btn btn-ghost" style={{ padding: '3px 10px', fontSize: 11 }} to={jobPath(j)}>打开</Link>
            </div>
          ))}
          {jobs.length > recent.length && (
            <p className="pixel small muted" style={{ textAlign: 'right', margin: '8px 0 0' }}>
              共 {jobs.length} 个任务，显示最近 {recent.length} 个
            </p>
          )}
        </div>
      )}

      {!loading && !error && running.length === 0 && recent.length === 0 && (
        <div className="panel hall-empty">
          <span className="hall-empty-icon pixel">♠</span>
          <p>还没有研究记录，可以先从你感兴趣的领域开始召唤。</p>
          <Link className="btn" to="/summon">去召唤</Link>
        </div>
      )}

      {health && (health.scholartrace === false || health.scholaranalysis === false || health.webresearch === false) && (
        <p className="muted small" style={{ textAlign: 'center', marginTop: 18 }}>
          部分检索服务暂时不可用：ScholarTrace {health.scholartrace ? '✓' : '✗'} · ScholarAnalysis {health.scholaranalysis ? '✓' : '✗'} · WebResearch {health.webresearch ? '✓' : '✗'}
        </p>
      )}
    </div>
  )
}

function jobTitle(j: JobListItem): string {
  const p = j.params
  const text = (p.topic ?? p.question ?? p.proposal ?? '') as string
  if (text) return text.slice(0, 70)
  if (p.idea_id) return `灵感 ${(p.idea_id as string).slice(0, 18)}`
  if (p.card_id) return `研究卡 ${p.card_id as string}`
  if (p.run_id) return `续跑 ${(p.run_id as string).slice(0, 24)}`
  return j.id
}

function statusLabel(s: string) {
  return { running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消', paused: '已暂停' }[s] ?? s
}

export function jobPath(j: JobListItem): string {
  // 已关联 run 的进行中任务:详情页有实时进度(法阵/仪表/日志);
  // 只有刚提交还没关联上的才回模式页
  if (j.run_dir) return `/runs/${j.run_dir}`
  if (j.mode === 'resume' && typeof j.params.run_id === 'string') return `/runs/${j.params.run_id}`
  const page = j.mode === 'discover' ? '/summon' : j.mode === 'develop' ? '/trial' : '/judgment'
  return `${page}?job=${encodeURIComponent(j.id)}`
}
