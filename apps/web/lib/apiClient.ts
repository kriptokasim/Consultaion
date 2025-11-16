const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

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

  if (typeof window !== "undefined" && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrfToken = getCsrfTokenFromCookie();
    if (csrfToken) {
      (init.headers as Record<string, string>)["X-CSRF-Token"] = csrfToken;
    }
  }

  const res = await fetch(url, init);
  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");

  if (!res.ok) {
    if (isJson) {
      const errorBody = await res.json().catch(() => ({}));
      const detail = (errorBody as any)?.detail || res.statusText;
      throw new Error(`API ${res.status} ${res.statusText}: ${detail}`);
    }
    throw new Error(`API ${res.status} ${res.statusText}`);
  }

  if (!isJson) {
    return undefined as unknown as TResponse;
  }

  return (await res.json()) as TResponse;
}
