# Scan 1 — Triage Report

**Date**: Patchset 150–151
**Scanner**: gitleaks + custom rules

## Fixed

| ID | File | Description | Fix |
|---|---|---|---|
| GITLEAKS-01 | `apps/api/run_migration.py` | Hardcoded Supabase pooler password | File deleted; credential must be rotated manually |
| BUG-API-2 | `apps/api/routes/debates/streaming.py` | SSE CORS header fell back to `*` when `WEB_APP_ORIGIN` unset | Added allowlist validation; fail-closed in production |
| BUG-AUTH-5 | `apps/api/routes/auth.py` + `auth.py` | Stale module-level constants `COOKIE_NAME` etc. read once at import time | Added helpers that read settings at call time |
| BUG-AUTH-6 | `apps/web/app/api/auth/google/callback/route.ts` | OAuth redirect path unsanitized | Created `apps/web/lib/security/internalPath.ts` sanitizer |
| BUG-AUTH-7 | `apps/web/app/(marketing)/methodology/page.tsx` | `dangerouslySetInnerHTML` on translation strings | Replaced with plain text rendering |
| CSP-01 | `apps/web/next.config.ts` | CSP too strict (no `unsafe-inline`/`unsafe-eval` for Next.js bootstrap) | Restored working enforced CSP; strict policy in `Content-Security-Policy-Report-Only` |

## False Positive

| ID | File | Description | Verdict |
|---|---|---|---|
| GITLEAKS-FP-01 | `.gitleaks.toml` | Supabase pooler credential string appears in test fixtures | Suppressed in `.gitleaks.toml`; credential is a placeholder, not real |

## Deferred

| ID | File | Description | Rationale |
|---|---|---|---|
| SSRF-01 | `apps/api/auth.py` | Avatar URL SSRF | Server does not fetch avatar URLs — only stores and displays (see `docs/adr/001-avatar-ssrf.md`) |
| LINT-01 | Various | Pre-existing mypy type errors (lenient mode) | Not regressions; strict mypy deferred to dedicated phase |

## Notes

- The leaked Supabase credential in `run_migration.py` remains in Git history. **Manual secret rotation is required.**
- `make scan-secrets` runs `gitleaks detect --source . --redact --verbose` to catch future leaks.
