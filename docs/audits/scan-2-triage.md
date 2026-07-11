# Scan-2 Triage Document

**Patchset:** PS152
**Date:** 2026-07-11
**Purpose:** Document disposition of each scanner finding from the second review.

---

## FIXED IN PS152

- **Missing persisted deletion_requested_at** — Added `deletion_requested_at` column to User model with Alembic migration.
- **Broken GDPR request/cancel/process workflow** — Rewrote `gdpr/service.py`: request keeps user active, cancellation works, scheduled processing uses `FOR UPDATE SKIP LOCKED`.
- **Invalid GDPR field names** — Removed references to non-existent `user.name`, `user.google_id`, `user.anonymized_at`.
- **NULL password_hash during scheduled anonymization** — Erasure service now sets `password_hash` to a valid PBKDF2 hash.
- **Scheduled/immediate erasure implementation drift** — Created `services/account_erasure.py` as single canonical implementation; both paths now call it.
- **Cross-worker hosted-credit correctness** — Replaced in-memory asyncio lock with `UPDATE ... WHERE hosted_credits_used + cost <= limit` atomic conditional update.
- **WEB_APP_ORIGIN snapshot** — Replaced module-level `WEB_APP_ORIGIN = settings.WEB_APP_ORIGIN` with `get_web_app_origin()` runtime accessor.
- **gitleaks `regexs` typo** — Fixed `[[allowlist.regexs]]` to `[[allowlist.regexes]]`.
- **Raw frontend API error display** — Applied `normalizeError()` to SynthesisChallenge and OracleWorkspace error handlers.
- **Unbounded streaming preview buffer** — Added `MAX_STREAM_BUFFER_CHARS = 120_000` limit with `truncated` flag in streaming reducer.

## ALREADY FIXED (Before PS152)

- **Gemini key in header** — Fixed in PS151 (provider key transport unchanged).
- **SSE wildcard removal and Origin validation** — Fixed in PS151.
- **JWT decode detail** — Already returns generic "Invalid or malformed token" (PS151).
- **Nginx security headers** — Already present in `infra/nginx.conf`.
- **Registration response does not contain JWT** — Registration returns serialized user via `serialize_user()`, auth delivered via HttpOnly cookie.
- **Tailwind lib/hooks paths** — Already configured in `tailwind.config.ts`.
- **Oracle React-text rendering** — Oracle node content rendered via React text nodes, not `dangerouslySetInnerHTML`.
- **DecisionReport HTML escaping** — Uses `sanitizeMarkdown()` which escapes HTML.
- **Immediate-delete random valid password hash** — Already uses `hash_password(secrets.token_urlsafe(32))`.
- **Single GOOGLE_AUTH_URL assignment** — Only one definition exists in `routes/auth.py`.

## CONFIRMED SAFE / FALSE-POSITIVE

- **Nginx has zero headers** — False-positive. `infra/nginx.conf` contains security headers (X-Content-Type-Options, X-Frame-Options, etc.).
- **Registration returns access_token** — False-positive. `serialize_user()` does not include token; auth is via cookie only.
- **Oracle uses unsafe raw markdown** — False-positive. Oracle nodes are React text nodes, not `dangerouslySetInnerHTML`.
- **Duplicate GOOGLE_AUTH_URL** — False-positive. Single definition exists.
- **Tailwind lib/hooks paths absent** — False-positive. Paths already configured.
- **API CSP is the cause of the Vercel homepage blank screen** — False-positive. API CSP and browser CSP are separate systems; PS150 fixed the browser CSP.
- **`setdefault` alone is a complete multi-worker credit fix** — False-positive. `setdefault` is process-local; PS152 adds DB-level atomic UPDATE.

## DEFERRED

- **Strict nonce-based Next.js CSP** — Deferred. Current PS150 CSP is functional; nonce-based CSP requires significant refactoring and is not a security regression.
- **Git-history rewrite after credential rotation** — Deferred. Requires coordination with team; credentials already rotated.
- **Full redesign of API-client redirect architecture** — Deferred. Out of scope for security patchset.
- **Unrelated graph-viewer tooling findings** — Deferred. Not security-relevant to current scope.
