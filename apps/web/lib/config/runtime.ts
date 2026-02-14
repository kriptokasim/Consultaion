/**
 * Runtime Config — Single Source of Truth for URL Construction
 *
 * All URL construction in the frontend MUST flow through this module.
 * No other file should concatenate base URLs.
 *
 * Environment variables:
 *   NEXT_PUBLIC_APP_URL  — canonical web origin (e.g. https://web.consultaion.com)
 *   NEXT_PUBLIC_API_URL  — canonical API origin (e.g. https://api.consultaion.com)
 */

// ---------------------------------------------------------------------------
// App Origin — used for canonical URLs, OG tags, absolute redirects
// ---------------------------------------------------------------------------
export const APP_ORIGIN =
  process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";

// ---------------------------------------------------------------------------
// API Origin — used for all backend calls
//
// In the browser during production builds Vercel proxies /api/* to the backend,
// so we use the relative "/api" prefix. During SSR or local dev we connect
// directly to the API server.
// ---------------------------------------------------------------------------
export const API_ORIGIN =
  typeof window !== "undefined" && process.env.NODE_ENV === "production"
    ? "/api"
    : process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Build an absolute API URL for a given path.
 *
 * @example apiUrl("/debates")        → "https://api.consultaion.com/debates"
 * @example apiUrl("/debates/123")    → "https://api.consultaion.com/debates/123"
 */
export function apiUrl(path: string): string {
  const base = API_ORIGIN.replace(/\/+$/, "");
  const segment = path.startsWith("/") ? path : `/${path}`;
  return `${base}${segment}`;
}

/**
 * Build an absolute app URL for a given path (canonical / OG / redirects).
 *
 * @example absoluteUrl("/dashboard")  → "https://web.consultaion.com/dashboard"
 */
export function absoluteUrl(path: string): string {
  const base = APP_ORIGIN.replace(/\/+$/, "");
  const segment = path.startsWith("/") ? path : `/${path}`;
  return `${base}${segment}`;
}
