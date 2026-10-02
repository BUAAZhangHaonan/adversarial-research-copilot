/* fetch 封装：同源 cookie、统一错误 */

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!resp.ok) {
    if (resp.status === 401 && path !== '/api/auth/login') {
      window.dispatchEvent(new Event('arc:unauthorized'))
    }
    let detail = `HTTP ${resp.status}`
    try {
      const body = await resp.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* ignore */ }
    throw new ApiError(detail, resp.status)
  }
  return resp.json() as Promise<T>
}

export const api = {
  login: (username: string, password: string) =>
    request<{ user: { username: string; is_admin: boolean } }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<{ ok: boolean }>('/api/auth/logout', { method: 'POST' }),
  me: () => request<{ username: string; is_admin: boolean }>('/api/auth/me'),
  health: () => request<import('./types').Health>('/api/health'),
  runs: () => request<{ runs: import('./types').RunSummary[] }>('/api/runs'),
  runVisibility: (dir: string) =>
    request<{ visible: boolean; current_run_id: string; version_revision: number }>(`/api/runs/${encodeURIComponent(dir)}/visibility`),
  jobVisibility: (id: string) =>
    request<{ visible: boolean; current_run_id: string | null; version_revision: number }>(`/api/jobs/${encodeURIComponent(id)}/visibility`),
  runDetail: (dir: string) => request<import('./types').RunDetail>(`/api/runs/${dir}`),
  runFile: (dir: string, name: string) =>
    request<{ name: string; content: string }>(
      `/api/runs/${dir}/file?name=${encodeURIComponent(name)}`),
  submitJob: (mode: string, params: Record<string, unknown>) =>
    request<{ job_id: string }>('/api/jobs', {
      method: 'POST',
      body: JSON.stringify({ mode, params }),
    }),
  jobStatus: (id: string) => request<import('./types').JobStatus>(`/api/jobs/${id}`),
  cancelJob: (id: string) => request<{ id: string; status: string }>(`/api/jobs/${id}`, { method: 'DELETE' }),
  jobs: () => request<{ jobs: import('./types').JobListItem[] }>('/api/jobs'),
}
