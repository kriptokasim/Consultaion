import { fetchWithAuth } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ListParams = {
  status?: string;
  limit?: number;
  offset?: number;
};

const baseFetcher = async (url: string, init?: RequestInit) =>
  fetch(`${API}${url}`, { cache: "no-store", credentials: "include", ...init });

export class ApiError extends Error {
  status: number;
  body: any;

  constructor(message: string, status: number, body?: any) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, init?: RequestInit, opts?: { auth?: boolean }) {
  const fetcher = opts?.auth && typeof fetchWithAuth === "function" ? fetchWithAuth : baseFetcher;
  const res = await fetcher(path, init);
  if (!res.ok) {
    let body: any = null;
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      body = await res.json().catch(() => null);
    } else {
      body = await res.text().catch(() => null);
    }
    throw new ApiError(`Request failed: ${res.status}`, res.status, body);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await res.json()) as T;
  }
  return undefined as T;
}

export async function getDebates(params: ListParams = {}) {
  const query = new URLSearchParams(
    Object.entries(params)
      .filter(([, value]) => value !== undefined && value !== null)
      .map(([key, value]) => [key, String(value)]),
  );
  const suffix = query.size ? `?${query.toString()}` : "";
  return request<any>(`/debates${suffix}`, undefined, { auth: true });
}

export async function getDebate(id: string) {
  return request<any>(`/debates/${id}`, undefined, { auth: true });
}

export async function getReport(id: string) {
  return request<any>(`/debates/${id}/report`, undefined, { auth: true });
}

export async function startDebate(payload: { prompt: string; config?: any }) {
  return request<{ id: string }>(
    `/debates`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    { auth: true },
  );
}

export function streamDebate(id: string) {
  return new EventSource(`${API}/debates/${id}/stream`, { withCredentials: true });
}

export async function getEvents(id: string) {
  return request<any>(`/debates/${id}/events`, undefined, { auth: true });
}

export async function getMembers() {
  return request<any>("/config/members");
}

export async function getDebateMembers(id: string) {
  return request<any>(`/debates/${id}/members`, undefined, { auth: true });
}

export async function getMyDebates(params: ListParams = {}) {
  const query = new URLSearchParams(
    Object.entries(params)
      .filter(([, value]) => value !== undefined && value !== null)
      .map(([key, value]) => [key, String(value)]),
  );
  const suffix = query.size ? `?${query.toString()}` : "";
  return request<any>(`/debates${suffix}`, undefined, { auth: true });
}

export type TeamSummary = {
  id: string;
  name: string;
  role?: string;
  created_at?: string;
};

export async function getTeams() {
  const payload = await request<{ items?: TeamSummary[] }>(`/teams`, undefined, { auth: true });
  return payload?.items ?? [];
}

export async function assignDebateTeam(debateId: string, teamId: string | null) {
  return request(
    `/debates/${debateId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ team_id: teamId ?? "" }),
    },
    { auth: true },
  );
}

export type AuditLogEntry = {
  id: number;
  action: string;
  user_id?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  meta?: Record<string, any> | null;
  created_at: string;
};

export async function getAuditLogs(limit = 100) {
  const params = new URLSearchParams({ limit: String(limit) });
  const payload = await request<{ items?: AuditLogEntry[] }>(`/admin/logs?${params.toString()}`, undefined, {
    auth: true,
  });
  return payload?.items ?? [];
}

export type LeaderboardEntry = {
  persona: string;
  category?: string | null;
  elo: number;
  stdev: number;
  n_matches: number;
  win_rate: number;
  ci: { low: number; high: number };
  last_updated?: string | null;
  label?: string;
  badge?: string | null;
};

export async function getLeaderboard(params: { category?: string; minMatches?: number; limit?: number } = {}) {
  const search = new URLSearchParams();
  if (params.category !== undefined) {
    search.set("category", params.category);
  }
  if (typeof params.minMatches === "number") {
    search.set("min_matches", String(params.minMatches));
  }
  if (typeof params.limit === "number") {
    search.set("limit", String(params.limit));
  }
  const suffix = search.size ? `?${search.toString()}` : "";
  const payload = await request<{ items?: LeaderboardEntry[] }>(`/leaderboard${suffix}`);
  return payload?.items ?? [];
}

export async function getLeaderboardPersona(persona: string, category?: string) {
  const suffix =
    category !== undefined ? `?category=${encodeURIComponent(category ?? "")}` : "";
  return request<LeaderboardEntry>(`/leaderboard/persona/${encodeURIComponent(persona)}${suffix}`);
}
