import { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import type { DiscoveryCard } from '../types'
import { DECISION_LABEL, IDEA_STATUS_LABEL, TRIAGE_LABEL, rarityOf, RARITY_LABEL, type Rarity } from '../rarity'
import { DecisionIcon } from './icons'

interface Props {
  card: DiscoveryCard
  /** 初始是否背面(用于翻牌动画) */
  faceDown?: boolean
  onClick?: (card: DiscoveryCard) => void
  width?: number
  className?: string
  /** 卡背稀有度辉光(开包悬念：看到光猜稀有度，翻开验证) */
  backGlow?: boolean
}

const DECISION_STARS: Record<string, number> = { lead: 5, discuss: 4, park: 2, drop: 1 }

/** 研究灵感卡：背面 ARC 纹章，正面稀有度 + 预研结论花色 + 抽卡序号 */
export default function IdeaCardView({ card, faceDown = false, onClick, width = 172, className = '', backGlow = false }: Props) {
  const [down, setDown] = useState(faceDown)
  useEffect(() => { setDown(faceDown) }, [faceDown, card.idea_id])
  const tiltRef = useRef<HTMLDivElement>(null)
  const reducedMotion = useReducedMotion()
  const rarity = rarityOf(card)
  const title = card.presentation?.presentation_title || card.seed?.title || '（未命名灵感）'
  const decision = card.note?.decision
  const stars = DECISION_STARS[decision ?? ''] ?? 0
  const shortId = card.idea_id.replace(/^idea_/, '').slice(0, 6)
  const interactive = down || !!onClick
  const activate = () => {
    if (down) { setDown(false); return }
    onClick?.(card)
  }

  // 鼠标跟随 3D 倾斜(直接写 style,避免 60fps setState)
  const onTilt = (e: React.MouseEvent<HTMLDivElement>) => {
    if (reducedMotion) return
    const el = tiltRef.current
    if (!el) return
    const r = e.currentTarget.getBoundingClientRect()
    const x = (e.clientX - r.left) / r.width - 0.5
    const y = (e.clientY - r.top) / r.height - 0.5
    el.style.transform = `rotateX(${(-y * 9).toFixed(2)}deg) rotateY(${(x * 11).toFixed(2)}deg)`
  }
  const untilt = () => {
    const el = tiltRef.current
    if (el) el.style.transform = 'rotateX(0deg) rotateY(0deg)'
  }

  return (
    <div
      className={`card-slot card-hover ${className}`}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-label={interactive ? down ? '翻开灵感卡' : `查看灵感卡：${title}` : undefined}
      style={{ ['--card-w' as string]: `${width}px` }}
      onMouseMove={onTilt}
      onMouseLeave={untilt}
      onClick={activate}
      onKeyDown={(e) => { if (interactive && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); activate() } }}
    >
      <div ref={tiltRef} className="card-tilt">
        <motion.div
          className="card3d"
          animate={{ rotateY: down ? 0 : 180 }}
          transition={reducedMotion ? { duration: 0 } : { type: 'spring', stiffness: 280, damping: 28 }}
          style={{ cursor: interactive ? 'pointer' : 'default' }}
        >
          <div className={`card-back ${backGlow ? `bg-${rarity}` : ''}`}>
            <div className="emblem">♠</div>
          </div>
          <div className={`card-face r-${rarity} ${rarity === 'X' ? 'card-shred' : ''}`}>
            <div className="card-head">
              <span className={`card-rarity r-${rarity}`}>{rarity}</span>
              <span className="pixel" style={{ fontSize: 10, color: '#6b6349' }}>
                {decision ? DECISION_LABEL[decision].split(' ')[0] : '待评估'}
              </span>
              <span className="card-id" title={card.idea_id}>{shortId}</span>
            </div>
            <div className="card-art">
              <DecisionIcon decision={decision} size={Math.round(width * 0.36)} />
              <span className="art-id">{rarity === 'SS' ? '★' : rarity}</span>
            </div>
            <div className="card-name" title={title}>{title}</div>
            <div className="card-stats">
              <span className="stars">
                {'★'.repeat(stars)}
                <span style={{ opacity: 0.3 }}>{'★'.repeat(5 - stars)}</span>
              </span>
              {card.note && (
                <span title="记录的相关工作数量" style={{ color: '#2c6aa8' }}>◈{card.note.nearest_work?.length ?? 0}</span>
              )}
              <span className="risk" title={card.note?.main_risk ?? ''}>
                {card.note ? '已记录风险' : TRIAGE_LABEL[card.triage?.action ?? ''] ?? IDEA_STATUS_LABEL[card.status] ?? card.status}
              </span>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

export { RARITY_LABEL }
export type { Rarity }
