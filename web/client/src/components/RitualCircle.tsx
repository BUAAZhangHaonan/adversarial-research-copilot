import type { ReactNode } from 'react'

/** 旋转法阵：外环刻度顺时针、内环符文逆时针、中心呼吸光。
 *  state: running 金绿 / paused 橙 / failed 红 / done 绿 */
export default function RitualCircle({ size = 200, state = 'running', core }: {
  size?: number
  state?: 'running' | 'paused' | 'failed' | 'done'
  core?: ReactNode
}) {
  const color = {
    running: 'var(--gold)',
    paused: 'var(--amber)',
    failed: 'var(--red)',
    done: 'var(--green-ok)',
  }[state]
  return (
    <div className={`ritual-circle rc-${state}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 200 200" width={size} height={size}>
        <defs>
          <radialGradient id="rc-glow">
            <stop offset="0" stopColor={color} stopOpacity="0.5" />
            <stop offset="1" stopColor={color} stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle cx="100" cy="100" r="96" fill="url(#rc-glow)" className="rc-breathe" />
        {/* 外环：刻度 */}
        <g className="rc-spin" style={{ transformOrigin: '100px 100px' }}>
          <circle cx="100" cy="100" r="88" fill="none" stroke={color} strokeWidth="2" strokeDasharray="4 10" opacity="0.95" />
          <circle cx="100" cy="100" r="80" fill="none" stroke={color} strokeWidth="1" opacity="0.55" />
          {Array.from({ length: 8 }).map((_, i) => (
            <line
              key={i}
              x1={100 + 76 * Math.cos((i * Math.PI) / 4)}
              y1={100 + 76 * Math.sin((i * Math.PI) / 4)}
              x2={100 + 88 * Math.cos((i * Math.PI) / 4)}
              y2={100 + 88 * Math.sin((i * Math.PI) / 4)}
              stroke={color} strokeWidth="2.4" opacity="0.7"
            />
          ))}
        </g>
        {/* 内环：三角与符文，反向旋转 */}
        <g className="rc-spin-rev" style={{ transformOrigin: '100px 100px' }}>
          <polygon
            points="100,32 158.6,133.5 41.4,133.5"
            fill="none" stroke={color} strokeWidth="1.6" opacity="0.55"
          />
          <polygon
            points="100,168 41.4,66.5 158.6,66.5"
            fill="none" stroke={color} strokeWidth="1.6" opacity="0.35"
          />
          <circle cx="100" cy="100" r="52" fill="none" stroke={color} strokeWidth="1.2" strokeDasharray="2 8" opacity="0.6" />
        </g>
      </svg>
      <div className="rc-core">
        <span className="rc-glyph">{core ?? '♠'}</span>
        <span className="rc-ring" />
      </div>
    </div>
  )
}
