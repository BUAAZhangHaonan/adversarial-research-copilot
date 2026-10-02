/* 卡面花色图标（decision 体系：lead=黑桃★领衔 discuss=红桃讨论 park=方块线索 drop=灰桃碎裂） */

export function DecisionIcon({ decision, size = 64 }: { decision?: string; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 100 100',
    xmlns: 'http://www.w3.org/2000/svg',
  }
  if (decision === 'lead') {
    // 黑桃 + 星：领衔
    return (
      <svg {...common} className="delta-icon">
        <g stroke="#161629" strokeWidth="5" strokeLinejoin="round">
          <path d="M50 10 C64 30 76 40 88 46 C76 54 64 66 50 92 C36 66 24 54 12 46 C24 40 36 30 50 10 Z" fill="#565472" />
          <path d="M50 24 C59 38 68 45 77 48 C68 52 59 60 50 76 C41 60 32 52 23 48 C32 45 41 38 50 24 Z" fill="#7b7399" opacity="0.8" />
        </g>
        <path d="M50 32 L54.7 42.6 L66 44 L57.5 51.8 L60 63 L50 57 L40 63 L42.5 51.8 L34 44 L45.3 42.6 Z" fill="#ffcf3f" stroke="#6b4a00" strokeWidth="3" strokeLinejoin="round" />
      </svg>
    )
  }
  if (decision === 'park') {
    // 方块：线索
    return (
      <svg {...common} className="delta-icon">
        <defs>
          <linearGradient id="dp" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#7fb1e8" />
            <stop offset="1" stopColor="#2c6aa8" />
          </linearGradient>
        </defs>
        <g stroke="#12304a" strokeWidth="5" strokeLinejoin="round">
          <path d="M50 12 L86 50 L50 88 L14 50 Z" fill="url(#dp)" />
          <path d="M50 30 L68 50 L50 70 L32 50 Z" fill="#ffd9" opacity="0.35" />
        </g>
        <circle cx="50" cy="50" r="9" fill="#fff3d0" stroke="#12304a" strokeWidth="4" />
      </svg>
    )
  }
  if (decision === 'drop') {
    // 灰桃：碎裂
    return (
      <svg {...common} className="delta-icon" style={{ opacity: 0.85 }}>
        <g stroke="#2e2c40" strokeWidth="5" strokeLinejoin="round">
          <path d="M50 10 C64 30 76 40 88 46 C76 54 64 66 50 92 C36 66 24 54 12 46 C24 40 36 30 50 10 Z" fill="#727184" />
        </g>
        <path d="M30 30 L46 46 M60 34 L50 50 M36 62 L52 52 M64 58 L54 68" stroke="#e8e2cc" strokeWidth="5" strokeLinecap="round" opacity="0.7" />
      </svg>
    )
  }
  // discuss / 默认：红桃
  return (
    <svg {...common} className="delta-icon">
      <g stroke="#5c1212" strokeWidth="5" strokeLinejoin="round">
        <path d="M50 88 C20 66 10 52 12 38 C14 24 26 16 38 20 C44 22 48 26 50 30 C52 26 56 22 62 20 C74 16 86 24 88 38 C90 52 80 66 50 88 Z" fill="#d94f4f" />
        <path d="M34 34 C28 34 24 39 25 44" stroke="#ffb0b0" strokeWidth="6" fill="none" strokeLinecap="round" />
      </g>
    </svg>
  )
}

export function SuitSpade({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M50 8 C64 30 78 40 86 48 C78 58 64 66 52 74 C56 82 62 88 68 92 L32 92 C38 88 44 82 48 74 C36 66 22 58 14 48 C22 40 36 30 50 8 Z"
        fill="#f4eed8"
        stroke="#242239"
        strokeWidth="6"
        strokeLinejoin="round"
      />
    </svg>
  )
}
