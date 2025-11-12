const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type ListParams = {
  status?: string
  limit?: number
  offset?: number
}

async function request<T>(path: string, init?: RequestInit) {
  const res = await fetch(`${API}${path}`, {
    cache: 'no-store',
    ...init,
  })
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`)
  }
  return (await res.json()) as T
}

export async function getDebates(params: ListParams = {}) {
  const query = new URLSearchParams(
    Object.entries(params)
      .filter(([, value]) => value !== undefined && value !== null)
      .map(([key, value]) => [key, String(value)]),
  )
  const suffix = query.size ? `?${query.toString()}` : ''
  return request<any>(`/debates${suffix}`)
}

export async function getDebate(id: string) {
  return request<any>(`/debates/${id}`)
}

export async function getReport(id: string) {
  return request<any>(`/debates/${id}/report`)
}

export async function startDebate(payload: { prompt: string; config?: any }) {
  return request<{ id: string }>(`/debates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function streamDebate(id: string) {
  return new EventSource(`${API}/debates/${id}/stream`)
}
