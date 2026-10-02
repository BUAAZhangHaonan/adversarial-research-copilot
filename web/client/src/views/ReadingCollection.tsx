import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { RunSummary } from '../types'
import { modeLabel } from './reading'
import './reading.css'

export default function ReadingCollection() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [filter, setFilter] = useState<string>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try { const result = await api.runs(); if (alive) { setRuns(result.runs); setError('') } }
      catch (reason) { if (alive) setError(String(reason)) }
      finally { if (alive) { setLoading(false); timer = setTimeout(poll, 5000) } }
    }
    poll()
    return () => { alive = false; clearTimeout(timer) }
  }, [])
  const shown = runs.filter((run) => filter === 'all' || run.mode === filter)
  return <div className="page reading-page">
    <header className="reading-library-header"><div><span className="reading-eyebrow">收藏</span><h1>研究记录</h1>
      <p>这里保存了每轮研究的发现和方案，可以先浏览结果，再打开感兴趣的卡片。</p></div><span className="reading-total">{runs.length} 份记录</span></header>
    <nav className="reading-filters" aria-label="研究阶段">
      {['all', 'discover', 'develop', 'debate'].map((mode) => <button key={mode} className={`btn ${mode === filter ? '' : 'btn-ghost'}`}
        aria-pressed={mode === filter} onClick={() => setFilter(mode)}>
        {mode === 'all' ? '全部' : modeLabel[mode as keyof typeof modeLabel]} <span>{mode === 'all' ? runs.length : runs.filter((run) => run.mode === mode).length}</span>
      </button>)}
    </nav>
    {loading && <p className="muted" role="status">正在读取研究记录…</p>}
    {error && <p className="error-text" role="alert">收藏暂时无法更新：{error}，正在重试。</p>}
    {!loading && !error && !shown.length && <p className="reading-empty">这个阶段还没有研究记录。<a href="#/summon">去召唤</a></p>}
    <div className="reading-run-list">{shown.map((run, index) => {
      const title = run.topic.trim().split('\n')[0] || '未命名讨论'
      const label = modeLabel[run.mode]
      return <button key={run.dir} className="panel run-row reading-run-row" onClick={() => navigate(`/runs/${run.dir}`)}>
        <span className="reading-run-number">{String(index + 1).padStart(2, '0')}</span>
        <span className="reading-run-description"><span className="reading-eyebrow">{label} · {run.status === 'COMPLETED' ? '已有结果' : '任务尚未完成'}</span>
          <strong className="reading-run-title">{title}</strong><span className="reading-run-purpose">{run.mode === 'discover' ? '本轮发现 · 灵感卡' : run.mode === 'develop' ? '方案概览 · 研究卡' : '核查结论 · 研究记录'}</span></span>
        <span className="reading-open">阅读 <span aria-hidden>↗</span></span>
      </button>
    })}</div>
  </div>
}
