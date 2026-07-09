/**
 * Centralized internal path sanitizer for OAuth redirects.
 *
 * Patchset 151: Prevents open-redirect and SSRF via malicious `next` params.
 * Used by Google OAuth login and callback routes.
 *
 * Rules:
 * - Allow only same-site path-like redirects
 * - Reject absolute URLs (http://, https://, etc.)
 * - Reject protocol-relative URLs (//evil.com)
 * - Reject backslashes (\)
 * - Reject dangerous schemes (javascript:, data:, vbscript:)
 * - Reject encoded protocol tricks (%2F%2F, %00, control chars)
 * - Preserve query string and hash for valid internal paths
 */
export function sanitizeInternalPath(
  value: string | null | undefined,
  fallback = "/dashboard"
): string {
  if (!value) return fallback;

  let decoded = value.trim();

  try {
    decoded = decodeURIComponent(decoded);
  } catch {
    return fallback;
  }

  // Must start with a single /
  if (!decoded.startsWith("/")) return fallback;
  if (decoded.startsWith("//")) return fallback;
  if (decoded.startsWith("/\\")) return fallback;

  // No backslashes anywhere (path traversal / UNC)
  if (decoded.includes("\\")) return fallback;

  // No dangerous schemes (javascript:, data:, vbscript:)
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(decoded)) return fallback;

  // No control characters (U+0000–U+001F, U+007F)
  if (/[\u0000-\u001F\u007F]/.test(decoded)) return fallback;

  // No null bytes
  if (decoded.includes("\0")) return fallback;

  // Validate via URL constructor (catches malformed percent-encoding)
  try {
    const url = new URL(decoded, "http://internal.local");
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return fallback;
  }
}
