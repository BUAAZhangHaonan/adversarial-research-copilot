import { useEffect, useState, type ReactNode } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api'

/** Keep open detail pages on the explicitly selected version, including finished runs. */
export default function CurrentRun({ children }: { children: ReactNode }) {
  const { dir = '' } = useParams()
  const { search } = useLocation()
  const jobId = new URLSearchParams(search).get('job')
  const key = dir || (jobId ? `job:${jobId}` : null)
  const navigate = useNavigate()
  const [visibleDir, setVisibleDir] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout>
    if (key === null) return
    setVisibleDir(null)
    setError('')
    const poll = async () => {
      try {
        let result
        try {
          result = dir ? await api.runVisibility(dir) : await api.jobVisibility(jobId!)
        } catch (capabilityError) {
          // Older servers lack metadata endpoints. Verify the normal authenticated
          // resource; never fall back on 401, 403, 410 or a service failure.
          if (!(capabilityError instanceof ApiError) || capabilityError.status !== 404) throw capabilityError
          if (dir) await api.runDetail(dir)
          else await api.jobStatus(jobId!)
          result = { visible: true, current_run_id: dir || null, version_revision: 0 }
        }
        if (!alive) return
        if (!result.visible) {
          setVisibleDir(null)
          if (result.current_run_id) navigate(`/runs/${encodeURIComponent(result.current_run_id)}`, { replace: true })
          return
        }
        setVisibleDir(key)
        setError('')
      } catch (e) {
        if (!alive) return
        setVisibleDir(null)
        setError(String(e))
      } finally {
        if (alive) timer = setTimeout(poll, 5000)
      }
    }
    poll()
    return () => { alive = false; clearTimeout(timer) }
  }, [dir, jobId, key, navigate])

  if (key === null || visibleDir === key) return <>{children}</>
  return <div className="page"><p className={error ? 'error-text' : 'muted'} role={error ? 'alert' : 'status'}>
    {error ? `结果暂时无法更新，正在重试：${error}` : '正在读取当前结果…'}
  </p></div>
}
