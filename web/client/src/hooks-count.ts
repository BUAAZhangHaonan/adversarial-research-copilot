import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'framer-motion'

/** 数字滚动:值变化时平滑过渡(用于耗时/计数/预算) */
export function useCountUp(target: number, durationMs = 500): number {
  const reducedMotion = useReducedMotion()
  const [value, setValue] = useState(target)
  const fromRef = useRef(target)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    if (reducedMotion) { fromRef.current = target; setValue(target); return }
    const from = fromRef.current
    if (from === target) return
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      const eased = 1 - Math.pow(1 - t, 3)
      const v = from + (target - from) * eased
      setValue(v)
      fromRef.current = v
      if (t < 1) rafRef.current = requestAnimationFrame(tick)
      else fromRef.current = target
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [target, durationMs, reducedMotion])

  return value
}
