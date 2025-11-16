import { apiRequest } from "@/lib/apiClient";
import { fetchWithAuth } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ListParams = {
  status?: string;
  limit?: number;
  offset?: number;
  q?: string;
};

export type ErrorBody = {
  detail?: string;
  code?: string;
  message?: string;
  reset_at?: string;
  [key: string]: any;
};

export type ListResponse<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

const baseFetcher = async (url: string, init?: RequestInit) =>
  fetch(`${API}${url}`, { cache: "no-store", credentials: "include", ...init });

const AUTH_STATUSES = new Set([401, 403]);

export class ApiError extends Error {
  status?: number;
  body: ErrorBody | string | null;

  constructor(message: string, status?: number, body?: ErrorBody | string | null) {
    super(message);
    this.status = status;
    this.body = body ?? null;
  }
}

const handleClientAuthRedirect = (status: number | undefined) => {
  if (typeof window !== "undefined" && status && AUTH_STATUSES.has(status)) {
    window.location.href = "/login";
  }
};

async function request<T>(path: string, init?: RequestInit, opts?: { auth?: boolean }) {
  const fetcher = opts?.auth && typeof fetchWithAuth === "function" ? fetchWithAuth : baseFetcher;
  const res = await fetcher(path, init);
  if (!res.ok) {
    let body: ErrorBody | string | null = null;
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      body = (await res.json().catch(() => null)) as ErrorBody | null;
    } else {
      body = await res.text().catch(() => null);
    }
    const error = new ApiError(`Request failed: ${res.status}`, res.status, body);
    handleClientAuthRedirect(error.status);
    throw error;
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

export async function getDebates(params: ListParams = {}, opts?: { auth?: boolean }) {
  const query = new URLSearchParams(
    Object.entries(params)
      .filter(([, value]) => value !== undefined && value !== null)
      .map(([key, value]) => [key, String(value)]),
  );
  const suffix = query.size ? `?${query.toString()}` : "";
  return request<ListResponse<any>>(`/debates${suffix}`, undefined, opts ?? { auth: true });
}

export async function getDebate(id: string) {
  return request<any>(`/debates/${id}`, undefined, { auth: true });
}

export async function getReport(id: string) {
  return request<any>(`/debates/${id}/report`, undefined, { auth: true });
}

export async function startDebate(payload: { prompt: string; config?: any }) {
  return apiRequest<{ id: string }>({
    method: "POST",
    path: "/debates",
    body: payload,
  });
}

export function streamDebate(id: string) {
  return new EventSource(`${API}/debates/${id}/stream`, { withCredentials: true });
}

export async function startDebateRun(debateId: string) {
  return apiRequest<{ status: string }>({
    method: "POST",
    path: `/debates/${debateId}/start`,
  });
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
  return getDebates(params, { auth: true });
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
  return apiRequest({
    method: "PATCH",
    path: `/debates/${debateId}`,
    body: { team_id: teamId ?? "" },
  });
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

export function isAuthError(error: unknown): error is ApiError {
  return error instanceof ApiError && !!error.status && AUTH_STATUSES.has(error.status);
}

export function getRateLimitInfo(error: unknown): { detail: string; resetAt?: string } | null {
  if (!(error instanceof ApiError) || error.status !== 429) return null;
  const body = error.body;
  const detail =
    body && typeof body === "object" && typeof body.detail === "string"
      ? body.detail
      : typeof body === "string"
        ? body
        : "Rate limit exceeded. Please wait and try again.";
  const resetAt =
    body && typeof body === "object" && typeof body.reset_at === "string" ? body.reset_at : undefined;
  return { detail, resetAt };
}
