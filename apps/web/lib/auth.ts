const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function buildHeaders(init?: HeadersInit): Promise<Headers> {
  const headers = new Headers(init);
  if (typeof window === "undefined") {
    const headerModule = await import("next/headers");
    const cookieStore = headerModule.cookies();
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
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error?.detail || "Login failed");
  }
  return res.json();
}

export async function logout() {
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

export async function fetchWithAuth(path: string, init?: RequestInit) {
  return authFetch(path, init);
}
