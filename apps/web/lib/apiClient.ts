import { API_ORIGIN } from "@/lib/config/runtime";

const API_BASE_URL = API_ORIGIN;

export class ApiClientError extends Error {
  status?: number;
  body: any;
  code?: string;
  hint?: string;
  retryable: boolean;
  retryAfterSeconds?: number;

  constructor(message: string, status?: number, body?: any) {
    super(message);
    this.status = status;
    this.body = body ?? null;
    this.code = body?.code;
    this.hint = body?.hint || body?.error?.hint;
    this.retryable = status === 429 || (status !== undefined && status >= 500) || status === 408;
    if (body?.retry_after) this.retryAfterSeconds = body.retry_after;
    if (body?.reset_at) {
      const ms = new Date(body.reset_at).getTime() - Date.now();
      if (ms > 0) this.retryAfterSeconds = Math.ceil(ms / 1000);
    }
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
  getRateLimitDetails(): { detail?: string; reset_at?: string; retry_after?: number; reason?: string } | null {
    if (!this.isRateLimitError()) return null;
    return {
      detail: this.body?.detail,
      reset_at: this.body?.reset_at,
      retry_after: this.body?.retry_after,
      reason: this.body?.reason || this.body?.code,
    };
  }

  /**
   * Get a user-friendly error message.
   */
  toUserMessage(): string {
    if (this.isRateLimitError()) {
      const seconds = this.retryAfterSeconds || 30;
      return `Rate limit reached \u2014 try again in ${seconds}s.`;
    }
    if (this.status === 503 || this.status === 502) {
      return "This model provider is temporarily unavailable. We tried available alternatives where possible.";
    }
    if (this.status === 403) {
      return "You do not have permission to perform this action.";
    }
    if (this.status === 0 || !this.status) {
      return "The request is taking longer than expected. Your run may still be processing.";
    }
    return this.message || "An unexpected error occurred.";
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
  /** Optional per-request timeout in milliseconds (Patchset 148 E2). */
  timeoutMs?: number;
  /** Optional external AbortSignal (Patchset 148 E2). */
  signal?: AbortSignal;
}

import { ApiListResponse, DebateDetail, DebateSummary, LeaderboardEntry, UserParticipationResponse } from './api/types';

// Helper function to make authenticated GET requests
async function fetchWithAuth<TResponse = unknown>(path: string): Promise<TResponse> {
  return apiRequest<TResponse>({ path, method: "GET" });
}

export async function getUserParticipation(): Promise<UserParticipationResponse> {
  return fetchWithAuth<UserParticipationResponse>("/users/me/participation");
}



export async function getDebatesList(params?: Record<string, any>): Promise<ApiListResponse<DebateSummary>> {
  // Filter out undefined/null values to prevent URLSearchParams from converting them
  // to literal "undefined"/"null" strings (which would cause backend filter mismatches)
  const cleanParams = params
    ? Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""))
    : undefined;
  const query = cleanParams ? new URLSearchParams(cleanParams).toString() : "";
  return fetchWithAuth(`/debates${query ? `?${query}` : ""}`);
}

export async function getLeaderboard(params?: Record<string, any>): Promise<{ items: LeaderboardEntry[] }> {
  const cleanParams = params
    ? Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""))
    : undefined;
  const query = cleanParams ? new URLSearchParams(cleanParams).toString() : "";
  return fetchWithAuth(`/leaderboard${query ? `?${query}` : ""}`);
}

export async function apiRequest<TResponse = unknown, TBody = unknown>(
  opts: ApiRequestOptions<TBody>,
): Promise<TResponse> {
  const { method = "GET", path, body, headers = {}, timeoutMs, signal: externalSignal } = opts;
  const url = path.startsWith("http") ? path : `${API_BASE_URL}${path}`;

  // E2: Compose abort signal with optional timeout
  const controller = new AbortController();
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  const abortHandler = () => controller.abort(externalSignal?.reason);

  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort(externalSignal.reason);
    } else {
      externalSignal.addEventListener("abort", abortHandler);
    }
  }
  if (timeoutMs) {
    timeoutId = setTimeout(() => controller.abort(new Error("Request timed out")), timeoutMs);
  }

  const init: RequestInit = {
    method,
    headers: {
      Accept: "application/json",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    credentials: "include",
    signal: controller.signal,
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
    // Auth is handled exclusively via session cookie (credentials: "include").
    // Do not inject tokens from browser storage — cookie-only is the secure path.
  }

  try {
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
  } catch (err: any) {
    // E2: Surface timeout errors properly
    if (err.name === "AbortError" && timeoutMs && !externalSignal?.aborted) {
      throw new ApiClientError(`Request timed out after ${timeoutMs}ms`, 408);
    }
    throw err;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
    if (externalSignal) {
      externalSignal.removeEventListener("abort", abortHandler);
    }
  }
}

// BUG-WEB-3: Removed `ApiClientError as ApiError` alias — it collided with
// the ApiError class in api.ts, causing instanceof checks to fail silently.
// Use ApiClientError directly if needed.
