import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { api, ApiError } from './api'
import type { Health, User } from './types'
import Login from './views/Login'
import Hall from './views/Hall'
import Summon from './views/Summon'
import Collection from './views/Collection'
import RunDetail from './views/RunDetail'
import CurrentRun from './components/CurrentRun'
import ReadingRun from './views/ReadingRun'
import ReadingCollection from './views/ReadingCollection'
import Trial from './views/Trial'
import Judgment from './views/Judgment'

const UserCtx = createContext<{ user: User | null; refresh: () => void }>({
  user: null,
  refresh: () => {},
})
export const useUser = () => useContext(UserCtx)

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [health, setHealth] = useState<Health | null>(null)
  const [authError, setAuthError] = useState('')
  const [healthError, setHealthError] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const authRequest = useRef(0)
  const navigate = useNavigate()

  const refresh = useCallback(() => {
    const request = ++authRequest.current
    setAuthError('')
    api.me()
      .then((value) => { if (request === authRequest.current) setUser(value) })
      .catch((e) => {
        if (request !== authRequest.current) return
        if (e instanceof ApiError && e.status === 401) setUser(null)
        else setAuthError('暂时无法连接研究所，请重试。')
      })
      .finally(() => { if (request === authRequest.current) setLoading(false) })
  }, [])

  useEffect(() => {
    const expired = () => {
      ++authRequest.current
      setUser(null)
      setHealth(null)
      setLoading(false)
      setAuthError('')
    }
    window.addEventListener('arc:unauthorized', expired)
    refresh()
    return () => { ++authRequest.current; window.removeEventListener('arc:unauthorized', expired) }
  }, [refresh])

  useEffect(() => {
    if (!user) return
    let alive = true
    let timer: ReturnType<typeof setTimeout>
    setHealth(null)
    setHealthError(false)
    const poll = async () => {
      try {
        const h = await api.health()
        if (alive) { setHealth(h); setHealthError(false) }
      } catch {
        if (alive) { setHealth(null); setHealthError(true) }
      } finally {
        if (alive) timer = setTimeout(poll, 15000)
      }
    }
    poll()
    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [user])

  const logout = async () => {
    if (loggingOut) return
    setLoggingOut(true)
    try {
      await api.logout()
      ++authRequest.current
      setUser(null)
      setHealth(null)
      setAuthError('')
      navigate('/login')
    } catch {
      setAuthError('登出失败，请重试。')
    } finally { setLoggingOut(false) }
  }

  if (loading) {
    return <div style={{ display: 'grid', placeItems: 'center', height: '100vh' }} className="pixel muted">正在加载页面…</div>
  }

  if (!user) {
    if (authError) return <div className="page"><div className="panel" role="alert">{authError} <button className="btn" onClick={refresh}>重试</button></div></div>
    return (
      <Routes>
        <Route path="/login" element={<Login onOk={refresh} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  const dots = (ok: boolean | undefined) => (
    <span style={{ color: ok == null ? 'var(--cream-dim)' : ok ? 'var(--green-ok)' : 'var(--red)' }}>●</span>
  )

  return (
    <UserCtx.Provider value={{ user, refresh }}>
      <div className="topbar">
        <a className="logo" href="#/">♠ ARC 卡牌研究所</a>
        <span className="chip service-status" title="显示检索工具的连接检查结果，实际运行情况可在任务日志中查看。" style={{ letterSpacing: '0.08em' }}>
          MCP {dots(health?.scholartrace)} {dots(health?.scholaranalysis)} {dots(health?.webresearch)}
          {!health && <span>{healthError ? '连接中断' : '检测中'}</span>}
        </span>
        {health && (
          <span className={`chip ${health.running_jobs > 0 ? 'warn' : ''}`} title={`当前任务数与可同时运行的任务上限`}>
            任务 {health.running_jobs}/{health.max_jobs}
          </span>
        )}
        <span className="spacer" />
        <nav className="primary-nav" aria-label="主导航">
        <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>大厅</NavLink>
        <NavLink to="/summon" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>召唤</NavLink>
        <NavLink to="/trial" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>试炼</NavLink>
        <NavLink to="/judgment" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>审判</NavLink>
        <NavLink to="/collection" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>收藏</NavLink>
        </nav>
        <span className="chip ok account-name" title={user.username}>{user.username}</span>
        <button className="btn btn-ghost logout-button" style={{ padding: '5px 12px', fontSize: '12px' }} disabled={loggingOut} onClick={logout}>
          {loggingOut ? '登出中…' : '登出'}
        </button>
      </div>
      {authError && <div className="page error-text" role="alert">{authError}</div>}
      <Routes>
        <Route path="/" element={<Hall health={health} />} />
        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="/summon" element={<CurrentRun><Summon /></CurrentRun>} />
        <Route path="/trial" element={<CurrentRun><Trial /></CurrentRun>} />
        <Route path="/judgment" element={<CurrentRun><Judgment /></CurrentRun>} />
        <Route path="/collection" element={<ReadingCollection />} />
        <Route path="/runs/:dir" element={<CurrentRun><ReadingRun /></CurrentRun>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </UserCtx.Provider>
  )
}
