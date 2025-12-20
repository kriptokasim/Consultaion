// Use /api prefix in browser (proxied by Vercel to Render)
// In SSR or local dev, use full URL
const API_BASE_URL =
  typeof window !== 'undefined' && process.env.NODE_ENV === 'production'
    ? '/api'  // Browser production: use Vercel proxy
    : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiClientError extends Error {
  status?: number;
  body: any;
  code?: string;

  constructor(message: string, status?: number, body?: any) {
    super(message);
    this.status = status;
    this.body = body ?? null;
    this.code = body?.code;
  }

  /**
   * Check if this error is a rate limit error.
   */
  isRateLimitError(): boolean {
    return this.status === 429 || this.code?.startsWith('rate_limit') || false;
  }

  /**
   * Get rate limit details if available.
   */
  getRateLimitDetails(): { detail?: string; reset_at?: string; reason?: string } | null {
    if (!this.isRateLimitError()) return null;
    return {
      detail: this.body?.detail,
      reset_at: this.body?.reset_at,
      reason: this.body?.reason || this.body?.code,
    };
  }
}

function getCsrfTokenFromCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith("csrf_token="));
  if (!match) return null;
  try {
    return decodeURIComponent(match.split("=")[1]);
  } catch {
    return match.split("=")[1] ?? null;
  }
}

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface ApiRequestOptions<TBody = unknown> {
  method?: HttpMethod;
  path: string;
  body?: TBody;
  headers?: Record<string, string>;
}

import { ApiListResponse, DebateDetail, DebateSummary, LeaderboardEntry } from './api/types';

// Helper function to make authenticated GET requests
async function fetchWithAuth<TResponse = unknown>(path: string): Promise<TResponse> {
  return apiRequest<TResponse>({ path, method: "GET" });
}

export async function getDebate(id: string): Promise<DebateDetail> {
  return fetchWithAuth(`/debates/${id}`);
}

export async function getDebatesList(params?: Record<string, any>): Promise<ApiListResponse<DebateSummary>> {
  const query = params ? new URLSearchParams(params).toString() : "";
  return fetchWithAuth(`/debates${query ? `?${query}` : ""}`);
}

export async function getLeaderboard(params?: Record<string, any>): Promise<{ items: LeaderboardEntry[] }> {
  const query = params ? new URLSearchParams(params).toString() : "";
  return fetchWithAuth(`/leaderboard${query ? `?${query}` : ""}`);
}

export async function apiRequest<TResponse = unknown, TBody = unknown>(
  opts: ApiRequestOptions<TBody>,
): Promise<TResponse> {
  const { method = "GET", path, body, headers = {} } = opts;
  const url = path.startsWith("http") ? path : `${API_BASE_URL}${path}`;

  const init: RequestInit = {
    method,
    headers: {
      Accept: "application/json",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    credentials: "include",
  };

  if (body !== undefined) {
    (init as any).body = JSON.stringify(body);
  }

  if (typeof window !== "undefined") {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      const csrfToken = getCsrfTokenFromCookie();
      if (csrfToken) {
        (init.headers as Record<string, string>)["X-CSRF-Token"] = csrfToken;
      }
    }

    // Fallback Auth: Inject Bearer token if present (for when cookies fail)
    const storedToken = localStorage.getItem("auth_token");
    if (storedToken) {
      (init.headers as Record<string, string>)["Authorization"] = `Bearer ${storedToken}`;
    }
  }

  const res = await fetch(url, init);
  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");

  if (!res.ok) {
    let detail = res.statusText;
    let body: any = null;
    if (isJson) {
      body = await res.json().catch(() => ({}));
      detail = (body as any)?.detail || detail;
    }
    throw new ApiClientError(`API ${res.status} ${res.statusText}: ${detail}`, res.status, body);
  }

  if (!isJson) {
    return undefined as unknown as TResponse;
  }

  return (await res.json()) as TResponse;
}
