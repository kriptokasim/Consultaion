# ADR-001: Avatar SSRF Mitigation — Server Does Not Fetch

## Status
Accepted

## Context
Google OAuth and Apple OAuth provide profile pictures via external URLs. There is a theoretical risk that an attacker could craft a malicious profile picture URL that targets internal services when the server fetches it (SSRF).

## Decision
**Do not fetch avatar URLs server-side.** The server only:
1. Stores the avatar URL string as-is in the database
2. Serves the URL to the client for display
3. Never performs outbound HTTP requests to the avatar URL

The client (browser) fetches and renders the avatar. If a user controls their own avatar URL (e.g., via account settings), the SSRF risk is self-directed and not exploitable against internal infrastructure.

## Rationale
- **No server-side fetch**: Since the server never fetches the avatar URL, there is no SSRF attack surface
- **Client-side only**: Browsers fetch the URL; browsers cannot reach internal network resources (same-origin policy applies)
- **Google/Apple controlled**: OAuth-provided avatar URLs come from trusted providers; users cannot control them
- **User-controlled avatars**: If future features allow custom avatar uploads, the upload should be proxied through the server with image type validation, not URL-based

## Consequences
- No server-side avatar proxy needed (reduced complexity)
- No DNS-based SSRF blocking needed for avatar URLs
- Future custom avatar upload feature must use server-side proxy with type validation
