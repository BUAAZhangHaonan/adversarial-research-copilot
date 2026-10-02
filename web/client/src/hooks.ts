import { useEffect, useState } from 'react'
import { api } from './api'
import type { JobStatus } from './types'

/** 轮询任务状态；running 时每 intervalMs 打一次，结束后停在最终态 */
export function useJob(jobId: string | null, intervalMs = 3000) {
  const [result, setResult] = useState<{ jobId: string | null; status: JobStatus | null; error: string }>({ jobId: null, status: null, error: '' })

  useEffect(() => {
    if (!jobId) return
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined
    setResult({ jobId, status: null, error: '' })
    const poll = async () => {
      try {
        const st = await api.jobStatus(jobId)
        if (!alive) return
        setResult({ jobId, status: st, error: '' })
        if (st.job.status === 'running') {
          timer = setTimeout(poll, intervalMs)
        }
      } catch (e) {
        if (!alive) return
        setResult((old) => ({ jobId, status: old.jobId === jobId ? old.status : null, error: String(e) }))
        timer = setTimeout(poll, intervalMs * 2)
      }
    }
    poll()
    return () => {
      alive = false
      if (timer) clearTimeout(timer)
    }
  }, [jobId, intervalMs])

  return result.jobId === jobId && jobId ? { status: result.status, error: result.error } : { status: null, error: '' }
}

export function useElapsed(startedIso: string | null | undefined, finishedIso?: string | null): number {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    setNow(Date.now())
    if (!startedIso || finishedIso) return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [startedIso, finishedIso])
  if (!startedIso) return 0
  return Math.max(0, Math.round(((finishedIso ? new Date(finishedIso).getTime() : now) - new Date(startedIso).getTime()) / 1000))
}

export function fmtSec(total: number): string {
  const m = Math.floor(total / 60)
  const s = total % 60
  return m > 0 ? `${m}分${String(s).padStart(2, '0')}秒` : `${s}秒`
}
