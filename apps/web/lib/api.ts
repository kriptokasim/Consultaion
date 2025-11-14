import { fetchWithAuth } from '@/lib/auth'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type ListParams = {
  status?: string
  limit?: number
  offset?: number
}

async function request<T>(path: string, init?: RequestInit, opts?: { auth?: boolean }) {
  const fetcher =
    opts?.auth && typeof fetchWithAuth === 'function'
      ? fetchWithAuth
      : async (url: string, init?: RequestInit) => fetch(`${API}${url}`, { cache: 'no-store', ...init })
  const res = await fetcher(path, init)
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
  return request<any>(`/debates${suffix}`, undefined, { auth: true })
}

export async function getDebate(id: string) {
  return request<any>(`/debates/${id}`, undefined, { auth: true })
}

export async function getReport(id: string) {
  return request<any>(`/debates/${id}/report`, undefined, { auth: true })
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

export async function getEvents(id: string) {
  return request<any>(`/debates/${id}/events`, undefined, { auth: true })
}

export async function getMembers() {
  return request<any>('/config/members')
}

export async function getDebateMembers(id: string) {
  return request<any>(`/debates/${id}/members`, undefined, { auth: true })
}

export async function getMyDebates(params: ListParams = {}) {
  const query = new URLSearchParams(
    Object.entries(params)
      .filter(([, value]) => value !== undefined && value !== null)
      .map(([key, value]) => [key, String(value)]),
  )
  const suffix = query.size ? `?${query.toString()}` : ''
  return request<any>(`/debates${suffix}`, undefined, { auth: true })
}
