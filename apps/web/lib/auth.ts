import { apiRequest } from "@/lib/apiClient";

// Use /api prefix in browser (proxied by Vercel to Render)
const API_BASE =
  typeof window !== 'undefined' && process.env.NODE_ENV === 'production'
    ? '/api'
    : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function buildHeaders(init?: HeadersInit): Promise<Headers> {
  const headers = new Headers(init);
  if (typeof window === "undefined") {
    const headerModule = await import("next/headers");
    const cookieStore = await headerModule.cookies();
    const cookieHeader = cookieStore
      .getAll()
      .map((cookie) => `${cookie.name}=${cookie.value}`)
      .join("; ");
    if (cookieHeader) {
      headers.set("Cookie", cookieHeader);
    }
  }
  return headers;
}

async function authFetch(path: string, init?: RequestInit) {
  const headers = await buildHeaders(init?.headers);
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
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
  // Clear all auth state from browser
  if (typeof window !== "undefined") {
    // Clear localStorage token
    localStorage.removeItem("auth_token");
    // Clear frontend-set cookie (used for cross-origin bootstrap after Google login)
    document.cookie = "consultaion_session=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; secure; samesite=lax";
  }
}

export async function fetchWithAuth(path: string, init?: RequestInit) {
  return authFetch(path, init);
}
