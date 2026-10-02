import { useCountUp } from '../hooks-count'

/* ============ 运行态仪式仪表盘 ============ */

/** 环形计数盘：抽卡 n/max;0% 时也保留极暗的弧，保持仪表形态 */
export function DrawDial({ started, max, active }: { started: number; max: number; active: boolean }) {
  const n = useCountUp(started)
  const pct = max > 0 ? Math.min(1, started / max) : 0
  const R = 54
  const C = 2 * Math.PI * R
  return (
    <div className={`dial ${active ? 'dial-active' : ''}`}>
      <svg viewBox="0 0 140 140" width={128} height={128}>
        <defs>
          <linearGradient id="dial-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#e6c58b" />
            <stop offset="1" stopColor="#a894dc" />
          </linearGradient>
        </defs>
        <circle cx="70" cy="70" r={R} fill="none" stroke="rgba(0,0,0,.4)" strokeWidth="11" />
        {max > 0 && (
          <circle
            cx="70" cy="70" r={R} fill="none"
            stroke="url(#dial-grad)" strokeWidth="11" strokeLinecap="round"
            opacity={pct === 0 ? 0.3 : 1}
            strokeDasharray={C} strokeDashoffset={C * (1 - (pct === 0 ? 0.04 : pct))}
            transform="rotate(-90 70 70)"
            style={{ transition: 'stroke-dashoffset .8s cubic-bezier(.2,1.4,.4,1)' }}
          />
        )}
      </svg>
      <div className="dial-center">
        <span className="dial-num num">{Math.round(n)}</span>
        {max > 0 && <span className="dial-max pixel">/ {max}</span>}
        <span className="dial-label pixel">{max > 0 ? '抽' : '轮'}</span>
      </div>
    </div>
  )
}

/** 预算表盘：弧形仪表，指针随消耗偏转；数据未上报时渲染占位盘，防布局跳动 */
export function BudgetDial({ spent, reserved, limit }: {
  spent: number | null; reserved: number | null; limit: number | null
}) {
  const hasData = spent != null && !!limit && limit > 0
  const burned = hasData ? (spent as number) + Math.max(0, reserved ?? 0) : 0
  const n = useCountUp(burned)
  const pct = hasData ? Math.min(1, burned / (limit as number)) : 0
  const hot = hasData && pct >= 0.8
  const R = 52
  const arcLen = (240 / 360) * 2 * Math.PI * R
  const angle = -210 + pct * 240

  return (
    <div title="显示已知费用加上当前预留金额，未确认的费用另行标示。" className={`dial budget-dial ${hot ? 'dial-hot' : ''} ${hasData ? '' : 'dial-placeholder'}`}>
      <svg viewBox="0 0 140 140" width={128} height={128}>
        <g transform="rotate(150 70 70)">
          <circle
            cx="70" cy="70" r={R} fill="none"
            stroke="rgba(0,0,0,.4)" strokeWidth="10" strokeLinecap="round"
            strokeDasharray={`${arcLen} ${2 * Math.PI * R}`}
          />
          {hasData && (
            <circle
              cx="70" cy="70" r={R} fill="none"
              stroke={hot ? '#ff5d5d' : '#ffb347'} strokeWidth="10" strokeLinecap="round"
              strokeDasharray={`${arcLen * pct} ${2 * Math.PI * R}`}
              style={{ transition: 'stroke-dasharray .8s cubic-bezier(.2,1.4,.4,1)' }}
            />
          )}
        </g>
        {hasData && (
          <g transform={`rotate(${angle} 70 70)`} style={{ transition: 'transform .8s cubic-bezier(.2,1.4,.4,1)' }}>
            <line x1="70" y1="70" x2="70" y2="26" stroke="#f4eed8" strokeWidth="3.5" strokeLinecap="round" />
            <circle cx="70" cy="70" r="5.5" fill="#f4eed8" />
          </g>
        )}
      </svg>
      <div className="dial-center">
        <span className="dial-num num dial-cny">{hasData ? `¥${n.toFixed(2)}` : '¥—'}</span>
        <span className="dial-max pixel">/ ¥{limit ? Math.round(limit) : '?'}</span>
        <span className="dial-label pixel">{hasData ? '费用与预留' : '待记录'}</span>
      </div>
    </div>
  )
}

/** 耗时数字块 */
export function ElapsedBlock({ seconds }: { seconds: number }) {
  const n = useCountUp(seconds, 350)
  const m = Math.floor(n / 60)
  const s = Math.floor(n % 60)
  const h = Math.floor(m / 60)
  return (
    <div className="elapsed-block">
      <div className="elapsed-time num">
        {h > 0 ? `${h}:${String(m % 60).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`}
      </div>
      <div className="dial-label pixel">已用时间</div>
    </div>
  )
}
