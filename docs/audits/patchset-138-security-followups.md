# Patchset 138 — Track D Security Fixes: Deferred Follow-Up Items

This document lists security items that were **specified** in the Track D brief for
Patchset 138 but **deferred** from implementation (per explicit instruction to skip them).

---

## D7 — CAPTCHA / Lockout Redesign

**Spec:** Design and implement CAPTCHA and/or progressive lockout for the auth
endpoints (login, register) to prevent brute-force credential stuffing.

**Why deferred:** The existing `increment_ip_bucket` / `record_429` flow in
`routes/auth.py` provides basic IP-based rate limiting, but lacks a proper
progressive lockout (escalating delays) or CAPTCHA challenge. A proper design
needs to consider:
- Turnstile / reCAPTCHA v3 integration
- Account-level vs IP-level lockout
- Lockout duration escalation (e.g. 30s → 5m → 30m → permanent)
- Admin unlock flow
- Logging and alerting for brute-force attempts

---

## D8 — OAuth State-Store Redesign

**Spec:** Replace the cookie-based OAuth state parameter in the Google OAuth flow
with a server-side state store (Redis-backed or database-backed).

**Why deferred:** Currently `routes/auth.py` uses `OAUTH_STATE_COOKIE` to pass
the state nonce to the callback. Cookie-based state is vulnerable to reflection.
A proper fix would:
- Store `(state_nonce, next_url, expires_at)` in Redis
- Use `httponly`, `secure`, `samesite=lax` cookies with a random session
- Validate the state server-side on callback
- TTL of 10 minutes on the stored state
- Cleanup of expired state entries

Current files affected: `routes/auth.py`, `routes/oauth_state.py` (if it exists).

---

## D9 — Proxy-Aware Rate-Limit Identity

**Spec:** Make rate-limit identity resolution aware of trusted proxy headers
(`X-Forwarded-For`, `CF-Connecting-IP`, `True-Client-IP`) so that when the app
is behind a reverse proxy, the originating client IP is used rather than the
proxy IP.

**Why deferred:** The current `increment_ip_bucket` in `routes/common.py`
uses `request.client.host` directly. The `settings.TRUSTED_PROXY_CIDRS` list
exists in `config.py` but is not wired into the rate-limit identity. A proper
fix would:
- Create a `get_client_ip(request)` utility that respects trusted proxy CIDRs
- Handle `X-Forwarded-For` (leftmost untrusted IP), `CF-Connecting-IP`, etc.
- Fall back to `request.client.host` when no proxy headers are present
- Log the resolved IP for audit
- Wire into both `increment_ip_bucket` and `WeightedRateLimitMiddleware`

Current files affected: `ratelimit.py`, `routes/common.py`, `middleware/weighted_rate_limit.py`.

---

## D10 — `__Host-` Cookie Migration

**Spec:** Migrate the auth and CSRF cookies to use the `__Host-` prefix for
hardened cookie security. This limits the cookie to the host-only origin (no
domain attribute) and requires `path=/` and `Secure` flag.

**Why deferred:** Changing cookie names (`consultaion_token` → `__Host-consultaion_token`)
is a breaking change that affects all existing sessions. Must be coordinated
with:
- Frontend cookie reads in `apps/web/`
- Logout on all devices (to delete old cookies)
- Staged rollout (set both old and new names, read both, write new)
- Backward compatibility for active sessions

Current files affected: `auth.py`, `config.py`, `routes/auth.py`.

---

## D11 — Full Dependency / Security Scanner Integration

**Spec:** Integrate a dependency scan (pip-audit, safety, or Snyk) into the CI
pipeline, and run a SAST scanner (semgrep, bandit) on the codebase.

**Why deferred:** Requires CI configuration changes and potentially a Snyk
account. The codebase has existing tools but no automated scanning pipeline
that blocks PRs on vulnerabilities.

---

## Implementation Notes

- All deferred items remain open security concerns.
- They were intentionally skipped per the Track D brief: "Do NOT implement
  deferred items."
- These should be re-triaged for Patchset 139 or a dedicated hardening sprint.
- Priority order (suggested): D9 > D7 > D8 > D10 > D11

---

*Generated: 2026-06-22 for Patchset 138 Track D delivery*
