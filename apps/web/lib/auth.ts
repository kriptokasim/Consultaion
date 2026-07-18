import { apiRequest } from "@/lib/apiClient";
import { API_ORIGIN } from "@/lib/config/runtime";
import type { RequestOptions } from "@/lib/api/types";

// Patchset 105: Use relative /api path on client to ensure cookie consistency
const API_BASE = typeof window === 'undefined' ? API_ORIGIN : "/api";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function csrfTokenFromCookieHeader(cookieHeader: string): string | null {
  const entry = cookieHeader
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith("csrf_token="));
  if (!entry) return null;
  const rawValue = entry.slice("csrf_token=".length);
  try {
    return decodeURIComponent(rawValue);
  } catch {
    return rawValue;
  }
}

async function buildHeaders(init?: HeadersInit, method = "GET"): Promise<Headers> {
  const headers = new Headers(init);
  let cookieHeader = "";
  if (typeof window === "undefined") {
    const headerModule = await import("next/headers");
    const cookieStore = await headerModule.cookies();
    cookieHeader = cookieStore
      .getAll()
      .map((cookie) => `${cookie.name}=${cookie.value}`)
      .join("; ");
    if (cookieHeader) {
      headers.set("Cookie", cookieHeader);
    }
  } else {
    cookieHeader = document.cookie;
  }

  if (UNSAFE_METHODS.has(method.toUpperCase()) && !headers.has("X-CSRF-Token")) {
    const csrfToken = csrfTokenFromCookieHeader(cookieHeader);
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }
  return headers;
}

async function authFetch(input: RequestInfo | URL, init?: RequestInit, options?: RequestOptions) {
  const path = typeof input === "string" ? input : input.toString();
  const headers = await buildHeaders(init?.headers, init?.method);
  const isAbsolute = path.startsWith("http://") || path.startsWith("https://");
  const alreadyPrefixed = path === API_BASE || path.startsWith(`${API_BASE}/`);
  const url = isAbsolute || alreadyPrefixed ? path : `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
    signal: options?.signal ?? init?.signal,
  });
  return response;
}

export async function getMe() {
  const res = await authFetch("/me");
  if (!res.ok) {
    return null;
  }
  return res.json();
}

export async function login(email: string, password: string) {
  return apiRequest({
    method: "POST",
    path: "/auth/login",
    body: { email, password },
  });
}

export async function logout() {
  await apiRequest({
    method: "POST",
    path: "/auth/logout",
  });
  // Clear the frontend bootstrap cookie set during Google OAuth redirect
  if (typeof window !== "undefined") {
    document.cookie = "consultaion_session=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; secure; samesite=lax";
  }
}

export async function fetchWithAuth(input: RequestInfo | URL, init?: RequestInit, options?: RequestOptions) {
  return authFetch(input, init, options);
}
