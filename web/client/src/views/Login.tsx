import { useState } from 'react'
import { motion } from 'framer-motion'
import { api, ApiError } from '../api'
import { SuitSpade } from '../components/icons'

export default function Login({ onOk }: { onOk: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.login(username, password)
      onOk()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '登录失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ display: 'grid', placeItems: 'center', height: '100vh', padding: 20 }}>
      <motion.div
        className="panel"
        style={{ width: 'min(400px, 100%)', textAlign: 'center' }}
        initial={{ scale: 0.9, y: 24, opacity: 0 }}
        animate={{ scale: 1, y: 0, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 240, damping: 20 }}
      >
        <div style={{ animation: 'floaty 3.5s ease-in-out infinite', display: 'inline-block', margin: '6px 0 10px' }}>
          <div
            style={{
              width: 92, height: 128, borderRadius: 10, border: '3px solid #14100a',
              display: 'grid', placeItems: 'center',
              background: 'radial-gradient(circle at 50% 42%, #343951 0 34%, #1f2235 34% 36%, #343951 36% 60%, #1f2235 60% 62%, #343951 62%)',
              boxShadow: '0 6px 0 rgba(0,0,0,.32), 0 12px 20px rgba(0,0,0,.4)',
            }}
          >
            <SuitSpade size={44} />
          </div>
        </div>
        <h1 className="pixel-big" style={{ color: 'var(--gold)', fontSize: 19, margin: '4px 0 2px', textShadow: '0 3px 0 rgba(0,0,0,.55)', letterSpacing: '0.02em' }}>
          ARC ◆ 卡牌研究所
        </h1>
        <p className="pixel muted" style={{ fontSize: 11, marginTop: 0 }}>RESEARCH IDEA · CARD DRAWS</p>

        <form onSubmit={submit} style={{ display: 'grid', gap: 12, marginTop: 18, textAlign: 'left' }}>
          <input
            className="input pixel" placeholder="用户名" autoComplete="username"
            value={username} onChange={(e) => setUsername(e.target.value)}
          />
          <input
            className="input pixel" placeholder="密码" type="password" autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)}
          />
          {error && <div className="error-text pixel" style={{ fontSize: 12 }}>✗ {error}</div>}
          <button className="btn btn-lg" type="submit" disabled={busy || !username || !password}>
            {busy ? '正在登录…' : '进入研究所'}
          </button>
        </form>
        <p className="muted small" style={{ marginTop: 14 }}>
          账号由管理员开通，研究任务会按实际调用计费。
        </p>
      </motion.div>
    </div>
  )
}
