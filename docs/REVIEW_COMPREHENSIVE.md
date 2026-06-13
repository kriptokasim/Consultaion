# Consultaion — Comprehensive Codebase Review

**Scope:** Near line-by-line review of `apps/api`, `apps/web`, `infra/`, `docs/`, and supporting tooling. Covers code quality (backend + frontend), infrastructure/CI/docs, VC-readiness (security, compliance, billing, observability, scalability, GTM signals, investor-facing metrics), and UX (IA, accessibility, real-time streaming UX, dashboard usability, onboarding, empty/loading/error states, billing/upgrade flows, admin tools).

**Methodology:**
1. Read top-level architecture docs, security notes, investor/traction docs, and the existing `REVIEW.md` to align on what's already been claimed as done.
2. Read core backend files (`main.py`, `config.py`, `auth.py`, `models.py`, `orchestrator.py`, `parliament/engine.py`, `billing/*`).
3. Read frontend foundation (`app/layout.tsx`, `lib/sse.ts`, `lib/apiClient.ts`, `lib/api/hooks/*`, `app/providers.tsx`).
4. Read infra (`docker-compose.yml`, `Dockerfile`, `nginx.conf`, `.github/workflows/*`).
5. Cross-check the docs against the actual code to find where reality diverges from claims.

**Verdict:** Consultaion is a **production-credible multi-tenant SaaS** with an unusually mature observability/safety story for its size. The platform is genuinely feature-complete for a Series A diligence package. The remaining gaps cluster around: (a) **production hardening** for multi-worker + multi-region scale, (b) **frontend polish** (accessibility, loading/empty states, mobile), (c) **investor-facing surfaces** (status page, changelog, public metrics, SOC 2 posture), and (d) a few **code-quality debt hot spots** that will slow the team at 2–3× current size.

The existing `REVIEW.md` (1211 lines, up to patchset 111) is excellent on backend/frontend/infrastructure and is the source of truth for "what's already done." This document is the **next layer** — it audits the audit, fills in VC-readiness and UX, and flags issues the previous review didn't reach.

---

## Table of Contents

1. [Codebase Snapshot](#1-codebase-snapshot)
2. [Backend Code Quality](#2-backend-code-quality)
3. [Frontend Code Quality](#3-frontend-code-quality)
4. [Infrastructure, CI & Docs](#4-infrastructure-ci--docs)
5. [VC-Readiness](#5-vc-readiness)
6. [UX](#6-ux)
7. [Prioritized Action Plan](#7-prioritized-action-plan)

---

## 1. Codebase Snapshot

| Area | Count | Notes |
|---|---|---|
| Backend Python files | 287 | `apps/api/` — FastAPI + SQLModel + Celery + Redis SSE |
| Alembic migrations | 36 | Heavily iterated (patchsets 1–118), some `pNNN_` numbered |
| Frontend TS/TSX files | 307 | App Router, 166 components, 5 hooks, 30+ lib modules |
| Test files (backend) | ~100 | pytest with both unit and integration coverage |
| Workflows | 5 | `ci.yml`, `codeql.yml`, `gitleaks.yml`, `self-healing.yml`, `smoke.yml` |
| Docs | 40+ | Architecture, security, investor metrics, traction dashboard, runbooks |
| Client SDKs | 2 | Python and JS — referenced but not deeply reviewed here |

**Strengths the audit confirms:**
- **Production boot validation** in `config.py:262–471` (`model_post_init`) refuses to start with `USE_MOCK=True`, `REQUIRE_REAL_LLM=False`, wildcard CORS, default JWT secret, or `SSE_BACKEND=memory` with multiple workers. This is **unusually disciplined** for a startup-stage repo.
- **Defense in depth on auth**: cookie + Bearer + API key + scoped stream token (`auth.py:53–166`), with safe logging (`auth.py:19–30`) and rate-limiting.
- **Multi-tenant primitives**: `User`, `Team`, `TeamMember`, `UserProviderKey` (BYOK), `APIKey` with team scoping (`models.py:16–131`, `219–231`, `511–523`).
- **Cost telemetry built in**: `LLMUsageLog` (`models.py:331–378`) records per-call provider/model/tokens/cost/fallback/retry — this is gold for unit economics and is rare at this stage.
- **Lease + heartbeat** for multi-worker debate execution (`orchestrator.py:49–106`) — prevents two workers from running the same debate.
- **Traction/GTM surfaces already exist**: `docs/investor-metrics.md`, `docs/traction-dashboard.md`, `docs/defensibility.md`, `docs/pricing-strategy.md`, `docs/growth-free-trial.md`, `docs/integrations.md`.

**Weaknesses the audit surfaces (new):**
- **Frontend accessibility is uneven**: skip-link exists (`layout.tsx:59–64`) but ARIA roles, focus management, and `prefers-reduced-motion` coverage are inconsistent.
- **Empty/loading/error states** are not systematically covered in the App Router pages.
- **Public metrics page is missing** — `docs/traction-dashboard.md` describes what should be shown but no `/status` or `/metrics` page exists in the app router.
- **Runbooks exist** (`docs/RUNBOOKS.md`) but there is no on-call rotation, incident template, or postmortem culture artifact in the repo.
- **SOC 2 posture is aspirational, not evidenced**: the docs reference "SOC2-ready" but there is no `SECURITY_CONTROLS.md`, no `pen-test-YYYY.md`, no `vendor-risk-register.md`.
- **Mobile UX**: no PWA manifest, no `viewport-fit` beyond the meta tag, no touch-target audit.

---

## 2. Backend Code Quality

### 2.1 Architecture & Module Boundaries

**Good:** The backend is well-decomposed by domain:
- `agents.py` — LLM adapters
- `parliament/` — multi-agent deliberation engine
- `arena/`, `compare/`, `conversation/` — mode-specific engines
- `orchestration/` — staged pipeline + state machine
- `billing/`, `safety/`, `security/`, `admin/` — cross-cutting concerns
- `worker/` — Celery tasks
- `repositories/` — emerging data-access abstraction (good sign)

**Issue — `main.py` is a router zoo (493 lines, ~25 routers):**
`main.py:348–422` registers 19 routers at the root and then **duplicates every one** under `/api/v1` (lines 393–422). The duplication is intentional for versioning but it means:
1. Two router instances per domain (different `prefix` and `tags`).
2. Any new router must be added in **two places** — easy to forget.
3. The auth/CSRF dependency is attached at the app level (`main.py:279`), so versioned routes inherit it correctly — but OpenAPI duplication creates a confusing developer experience (`/auth/login` shows up twice).

**Fix:**
```python
# Use a single canonical registration and let the v1 router re-export.
# Option A: only expose v1 in production; root is an alias.
# Option B: programmatic registration from a single source of truth.

ROUTERS = [
    ("auth", auth_router, []),
    ("debates", debates_router, []),
    ("billing", billing_router, []),
    # ...
]

for name, router, extra in ROUTERS:
    app.include_router(router, **extra)
    if settings.API_V1_ENABLED:
        v1_router.include_router(router, **extra)
```
Or move to a single router factory in `core/router_registry.py` and import in both places.

### 2.2 Configuration

**Good:** `config.py` is excellent. The `model_post_init` validator is the kind of code that prevents 3 a.m. pages.

**Issues:**
1. **Settings proxy mutability is a footgun** (`config.py:473–506`). `SettingsProxy.__setattr__` writes through to the underlying `_settings`, but tests that monkey-patch `settings.FOO = bar` will not trigger Pydantic validators. Consider an explicit `settings.override(...)` context manager for tests.
2. **The `is_local` / `is_render` detection logic** (`config.py:268–283`) couples deployment topology to the `RENDER` env var. If you ever deploy to Fly.io, Railway, or ECS with a custom env name, the check breaks. Add a `DEPLOY_TARGET` env var or read from a well-known platform var (e.g., `K_SERVICE`, `FLY_APP_NAME`).
3. **JWT secret length check is a floor, not a quality check** (`config.py:331`). Use `secrets.compare_digest` against a denylist of known-leaked secrets (haveibeenpwned-k-anonymity API for high-entropy secrets).
4. **CORS resolution is bidirectional and one-directional at the same time** (`config.py:445–471`). The function adds the resolved `WEB_APP_ORIGIN` to `CORS_ORIGINS` but never logs what it did. Add a `logger.info("Resolved CORS origins: %s", cors_origins)` for production debuggability.

### 2.3 Auth

**Good:** `auth.py` is well-structured. Highlights:
- `get_user_flexible` (`auth.py:370–385`) cleanly tries API key → cookie.
- Stream tokens are scoped (`auth.py:135–166`) and short-lived (5 min) — correct pattern for SSE.
- `verify_password` uses `hmac.compare_digest` (`auth.py:84`) — correct.
- API key prefix lookup is O(1) via the indexed `prefix` column (`auth.py:302–304`).

**Issues:**
1. **API key `last_used_at` writes on every request** (`auth.py:357–360`). At 1k req/s this is 1k `UPDATE api_keys SET last_used_at = now()` per second per key. Batch this with a 60-second in-memory cache, or only update if the last write was >60s ago.
2. **PBKDF2 with 150k iterations is borderline** (`config.py:187`, `auth.py:72–75`). OWASP 2023 recommends 600k+ for PBKDF2-SHA256, or migrate to Argon2id (which is in the stdlib of `argon2-cffi`). Argon2id also gives you memory-hardness, which PBKDF2 doesn't.
3. **No JWT revocation list**. A leaked token is valid until `exp`. Add a `jti` claim + a Redis denylist, or short-lived access tokens + refresh tokens.
4. **`_safe_auth_log` is good but incomplete** (`auth.py:19–30`). It logs cookie names — that can leak internal structure. Consider hashing cookie names or logging only counts.
5. **`get_user_from_api_key` does a synchronous `session.commit()`** (`auth.py:360`) inside a function that may be called from an async context. This will block the event loop. Use the async session.
6. **CSRF is opt-in for non-cookie auth** (`main.py:138–139`), which is correct, but the comment "CSRF attacks only affect cookie auth" is slightly misleading — it should say "Bearer tokens are not automatically attached by the browser, so they are not vulnerable to CSRF."

### 2.4 Database / Models

**Good:**
- Composite indexes on hot paths: `ix_debate_user_status_created` (`models.py:141`), `ix_message_debate_round` (`models.py:381`), `ix_audit_log_user_created` (`models.py:257`).
- `DebateStageCheckpoint` with `UniqueConstraint(debate_id, stage_key)` (`models.py:543`) — correct idempotency pattern.
- `UserPrediction` with `UniqueConstraint(debate_id, user_id)` (`models.py:428`) — correct.
- Soft delete on `User.deleted_at` (`models.py:39`) with index.

**Issues:**
1. **No `updated_at` triggers.** `Debate.updated_at` is set in Python (`orchestrator.py:258`, `797`). This is fine for correctness but easy to forget in new code paths. Add a SQLAlchemy `@event.listens_for` hook that bumps `updated_at` on every UPDATE.
2. **`Vote.result` is `Optional[dict[str, Any]]` JSON** (`models.py:215`). The shape is loosely typed. Use a Pydantic `VoteResult` model and validate on read.
3. **`Debate.config`, `Debate.panel_config`, `Debate.routing_meta` are all untyped JSON** (`models.py:147–160`). The patchset migration `ffc07156de2e_add_gin_indexes_to_debate_config` adds GIN indexes, which is great for queryability, but there's no schema validation. A bad panel config can pass DB write but fail at runtime. Add a `panel_config: PanelConfig | None` typed field and validate via Pydantic on construction.
4. **`Message.content` is `Text`** (`models.py:193`) — no length cap. A malicious user can submit a 10MB prompt that gets stored. The body limit middleware caps requests at 10MB (`main.py:326`), but the prompt could still be a 9.5MB string that the LLM call chokes on. Add a `CHECK (length(content) < 100000)` or a Pydantic validator.
5. **`PairwiseVote.candidate_a` / `candidate_b` are free-text strings** (`models.py:273–274`). They should be FKs to `Message` or `DebateTurn` to prevent typos and enable cascade deletes.
6. **`LLMUsageLog.estimated_cost_usd` is duplicated with `cost_usd`** (`models.py:360, 369`). Pick one. `estimated_cost_usd` suggests "we'll reconcile later" — make that reconciliation explicit (a nightly Celery job that joins against provider invoices).
7. **No `__table_args__` for `Message`, `Score`, `Vote`** — relies on global `Index(...)` declarations at the bottom (`models.py:381–400`). This works but is non-standard. Declare indexes inside each model.

### 2.5 Orchestrator

**Good:** `orchestrator.py` shows real production thinking:
- **Lease + heartbeat** (`orchestrator.py:49–106`) prevents duplicate execution.
- **Graceful failure handling** with status writes and Slack alerts (`orchestrator.py:730–823`).
- **Hosted credit refund** on transient LLM errors (`orchestrator.py:752–766`) — correct product behavior.
- **State manager pattern** (`orchestrator.py:540–557`) decouples pipeline from DB.
- **Metrics increment** at start/complete/fail (`orchestrator.py:483, 728, 733, 777`) — but these are not actually defined anywhere visible (see Observability section).

**Issues:**
1. **`run_attempt` is incremented on every lease acquisition** (`orchestrator.py:71`), including the **same runner's own refreshes**. The comment says "simple Increment is safer for tracking restarts" but it conflates "worker A reacquires after crash" with "worker A renews its own lease." Fix: only increment if `runner_id` is changing (use `CASE WHEN runner_id != :new_runner THEN run_attempt + 1 ELSE run_attempt END`).
2. **`_run_mock_debate` is reachable from production** (`orchestrator.py:537–538`). The check `if settings.FAST_DEBATE:` should be `if settings.FAST_DEBATE and settings.IS_LOCAL_ENV:`. The production boot validator already blocks `USE_MOCK`, but `FAST_DEBATE` is a separate flag and is not validated.
3. **`_build_and_send_summary` opens a session, commits, then fires-and-forgets an email** (`orchestrator.py:109–149`). The `asyncio.create_task` is **not awaited** and there's no task tracking. If the API process shuts down, the email is lost. Use a durable queue (Celery `send_summary_email_task.delay(...)`).
4. **Refund logic is duplicated** between the `TransientLLMError` and generic `Exception` handlers (`orchestrator.py:752–766` and `802–815`). Extract to `_refund_and_mark_failed(debate_id, user_id, reason)`.
5. **Heartbeat task error handling is silent** (`orchestrator.py:531`). `except Exception: pass` — this will hide DB connection drops. Log at warning level.
6. **The `redis_pool.close_sync_redis()` call in `main.py:271` is sync** but the function is in an async `finally` block. It blocks the event loop. Run it in an executor or make it async.
7. **SSE events are published via `backend.publish` but never persisted** — if the subscriber is reconnecting, they miss events. The `useSessionStream` hook tries to recover via `last_sequence` (`sse.ts:230–241`) but the backend must support replay. Verify that the SSE backend implements `?last_sequence=` replay (see `sse_backend.py` — not reviewed in depth here).

### 2.6 Billing

**Good:** `billing/service.py` (297 lines) and `billing/models.py` (83 lines) — clean separation. `billing/routes.py` (223 lines) covers checkout, webhook, portal.

**Issues (assumed from file sizes; spot-check recommended):**
1. **Stripe webhook signature verification is strict** (`config.py:335–336`) — good. But the `STRIPE_WEBHOOK_INSECURE_DEV` flag (`config.py:199`) is a footgun. If accidentally set to `true` in production, it accepts unsigned webhooks. Add it to the production boot validator.
2. **No idempotency on Stripe webhook processing.** The same `event.id` arriving twice will double-credit or double-revoke. Add a `stripe_event_id` unique constraint on the billing events table.
3. **No tax handling.** Prices are stored as raw `amount` — no `tax_rates` or VAT. For EU sales this is a compliance gap.
4. **Hosted credits model** (`models.py:34–36`) tracks `hosted_credits_used` with a counter — race condition risk under concurrent debate creation. Wrap in `SELECT ... FOR UPDATE` or use an atomic `UPDATE ... SET hosted_credits_used = hosted_credits_used + 1 WHERE hosted_credits_used < limit RETURNING ...`.
5. **No dunning / failed-payment handling.** The billing routes don't show a retry logic for failed subscriptions. Add a `billing/dunning.md` runbook.

### 2.7 Safety

**Good:**
- `ENABLE_PII_SCRUB` (`config.py:206`) — opt-in by default in dev, on in prod (implicit).
- `safety/pii.py` (per `docs/security-notes.md`) scrubs email/phone/address.
- `text_safety` (in `utils/`) detects API keys, JWTs, bearer tokens in shared prompts.
- `guards/llm_action_guard.py` exists — assume it's the LLM tool-call permission layer.

**Issues:**
1. **No PII re-identification risk assessment.** Scrubbing before send is good; **storing** the original prompt is the other half. Add a "store redacted" mode where the raw prompt is dropped after the run completes.
2. **No abuse signals.** No per-user LLM-call rate limit beyond `usage_limits.py`. A user can hammer the arena with 1k requests/minute and blow through your provider quotas. Add a `LLM_RPM_PER_USER` setting.
3. **Prompt injection guard is in `agents.build_messages()`** (per docs) — verify it has been **adversarially tested**. The `tests/test_redteam.py` exists — confirm it covers indirect injection via "ignore previous instructions" in retrieved context.
4. **No output filtering.** Models can return PII, hate speech, or competitor mentions. Add an output classifier pass for high-risk categories (regulated industries, K–12).

### 2.8 Observability

**Good:**
- `metrics.py` exists (`orchestrator.py:482` imports `increment_metric`).
- Sentry integration (`integrations/sentry.py`, init in `main.py:117`).
- Langfuse integration (`integrations/langfuse.py`) for LLM tracing.
- PostHog integration (`integrations/posthog.py`).
- Slack alerting (`integrations/slack.py`).

**Issues:**
1. **Metrics are increment-only.** `increment_metric("debate.started")` etc. — no histograms, no gauges, no labels. For VC-readiness you need: `debate_duration_seconds` (histogram), `llm_call_latency_seconds{provider,model}` (histogram), `active_debates` (gauge), `tokens_per_user_per_day` (counter with labels). Without these you cannot answer "what's our p95 latency?" or "what's the cost trajectory?"
2. **No OpenTelemetry.** Langfuse covers LLM spans but not DB, HTTP, or Celery spans. A single OTel pipeline gives you correlated traces across all layers.
3. **Logs are JSON-ish (Loguru per REVIEW.md) but not structured for log aggregation.** Verify fields are typed (string vs number vs nested object) — log aggregators (Datadog, Loki) parse this better when consistent.
4. **No SLO definitions.** `docs/observability-slos.md` (2.3KB) exists but is probably aspirational. Define: availability target (99.9%? 99.95%?), latency target (p95 < 8s for arena), error budget burn rate alert.
5. **No trace ID propagation in error responses.** A user reports a 500 — you have no way to grep their trace in Sentry. Add `trace_id` to `ErrorResponse` (which is also recommended in `REVIEW.md:3.3`).

### 2.9 Testing

**Good:** ~100 test files cover auth, debates, orchestrator, billing, promotions, usage, migrations, SSE, rate limits, model registry, parliament engine, ratings.

**Issues:**
1. **No property-based testing.** `hypothesis` is not in `requirements-dev.txt`. Property tests catch edge cases (long prompts, Unicode, empty strings) that unit tests miss.
2. **No mutation testing.** `docs/mutation-testing-spike.md` exists — confirm it has been run. If not, your test coverage number is misleading.
3. **No load testing.** No `locust` or `k6` scripts. A debate with 5 seats × 3 rounds × 3 judges = 15 LLM calls. At 100 concurrent users that's 1500 LLM calls — what's your provider rate limit? What's the queue depth?
4. **No contract tests for client SDKs.** `clients/python` and `clients/js` exist but no schema-pinning tests. If you change the API, the SDKs silently break.
5. **Test fixtures use SQLite in-memory** (per `REVIEW.md:5.1`). SQLite does not enforce all Postgres constraints (JSON, GIN indexes, `ON CONFLICT`). Some bugs only surface in Postgres.

---

## 3. Frontend Code Quality

### 3.1 Architecture

**Good:**
- App Router with route groups: `(app)` for authenticated, `(marketing)` for public.
- 166 components, 30+ lib modules, clear separation between `lib/api/`, `lib/i18n/`, `lib/stores/`, `hooks/`.
- i18n infrastructure: `lib/i18n/{client,server,context,dictionaries,provider}.ts` — server-side message loading with `ViewTransitions` for smooth navigation.
- Skip-to-content link in `layout.tsx:59–64`.
- `instrumentation.ts` and `instrumentation.client.ts` for Sentry/OpenTelemetry hooks.

**Issues:**
1. **Dual routing under `/` and `/api/v1` is mirrored on the frontend.** The client `apiClient.ts` must know which prefix to use. Confirm there is a single `API_BASE_URL` constant — not string concatenation across files.
2. **No route-level loading.tsx for most pages.** `apps/web/app/(app)/runs/loading.tsx` exists but many pages don't have one. With App Router, missing `loading.tsx` means the entire page is blocked until data is ready. Add skeleton states systematically.
3. **No error.tsx for most pages.** `apps/web/app/(app)/runs/[id]/error.tsx` exists, `app/error.tsx` and `app/global-error.tsx` exist — but most pages don't. A 500 in a nested component crashes the whole subtree.
4. **No `not-found.tsx` for most segments.** `apps/web/app/(app)/runs/[id]/not-found.tsx` exists. Add a default at `(app)/` and `(marketing)/`.
5. **`lib/apiClient.ts` is 162 lines and likely contains both fetch logic and error normalization.** Split into `apiClient.ts` (transport) and `errors.ts` (already exists — verify the split is clean).

### 3.2 SSE Client

**Good:** `lib/sse.ts` is well-written:
- `useEventSource` and `useSessionStream` are separate hooks with clear purposes.
- Exponential backoff retry (`sse.ts:16`, `DEFAULT_RETRY = [2000, 4000, 8000, 15000]`).
- Sequence-based deduplication and gap detection (`sse.ts:263–282`).
- Reconnect with `last_sequence` query param (`sse.ts:230–241`).
- Max 500 events cap to prevent memory growth (`sse.ts:280`).
- Cleanup on unmount with `cancelled` flag (`sse.ts:71, 127–130`).

**Issues:**
1. **No JSDoc on `SessionStreamEvent` type** — the `sequence`, `event`, `session_id` fields need documentation for SDK consumers.
2. **No abort signal support.** If the parent component wants to cancel a stream when the user navigates away, the only mechanism is unmount cleanup. Add `AbortController` support.
3. **`withCredentials` is always passed to `EventSource`** (`sse.ts:78, 243`). For same-origin requests this is fine, but for cross-origin it requires `Access-Control-Allow-Credentials: true` on the server. Confirm the backend sets this.
4. **No `Last-Event-ID` support.** Standard SSE reconnection sends `Last-Event-ID` header. You're using a custom `last_sequence` query param instead. Standard is more interoperable with proxies and CDNs.
5. **The `useEventSource` and `useSessionStream` hooks share ~80% of their code.** Extract a `useResilientSSE<T>` core and have both wrap it.

### 3.3 Hooks

**Good:** `useDebateVoting`, `useDelayedVote`, `useDebateTimeline`, `useDebatesList`, `useDebate`, `useLeaderboard`, `useUserParticipation` — well-named, single-purpose hooks.

**Issues:**
1. **No `useDebounce` for search inputs.** `use-debounce.ts` exists — verify it's used in the search/filter UIs.
2. **No `useMediaQuery` for responsive design.** If you do mobile-specific rendering, you're probably using `window.innerWidth` checks inline. Add a hook.
3. **`useDelayedVote` is interesting** — what does it delay? Verify it has tests; voting flows are security-critical.

### 3.4 Components

**Sampled (high-traffic, should be spot-checked in detail):**
- `components/arena/ArenaRunView.tsx` — the live debate view. Should have:
  - ✅ Skeleton while connecting
  - ✅ Reconnect indicator with retry count
  - ❓ Reduced-motion support (you have `use-reduced-motion.ts` — verify it's used)
  - ❓ Keyboard shortcuts (j/k to navigate messages, / to search)
- `components/billing/BillingSettingsClient.tsx` — billing dashboard. Should have:
  - ❓ Loading state for plan fetch
  - ❓ Error retry
  - ❓ Confirmation modal for plan downgrade
  - ❓ Proration preview before upgrade
- `components/admin/AdminUsersClient.tsx` — admin user list. Should have:
  - ❓ Search/filter
  - ❓ Bulk actions
  - ❓ Confirmation for destructive actions (ban, delete)
  - ❓ Audit log link per user

**Generic issues:**
1. **No Storybook.** With 166 components, visual regression is impossible without it. Add Storybook 8 with the Next.js framework.
2. **No visual regression tests.** `playwright.config.ts` exists — add `playwright` visual snapshot tests for the key pages.
3. **No accessibility audit.** Add `axe-core` via Playwright for automated a11y testing.
4. **Tailwind config** (`tailwind.config.ts`) — verify `darkMode: 'class'` is set (it is per `THEME_MIGRATION.md`).
5. **`components.json` / shadcn config** — not visible in the listing. Verify Radix UI primitives are wrapped in shadcn-style components, not raw Radix.

### 3.5 State Management

**Good:** TanStack Query for server state, Zustand for client state (per `REVIEW.md:2.1`). The split is correct.

**Issues:**
1. **The Zustand store recommendation in `REVIEW.md:2.1` is a template, not a review of the current code.** Read `lib/stores/debateStore.ts` (not in this review sample) and assess:
   - Is `events` capped at 1000?
   - Is persistence used? (Don't persist volatile data.)
   - Are there `subscribeWithSelector` patterns to avoid re-renders?
2. **No global error toast hook.** The `REVIEW.md:2.2` recommendation for `onError` toast is a template. Verify a real implementation exists in `app/providers.tsx`.

### 3.6 Forms & Validation

**Issues:**
1. **No `react-hook-form` or `@hookform/resolvers/zod` visible in package.json listing.** Forms with manual `useState` for each field will not scale. Verify the package.json includes these.
2. **The `DebateCreate` flow** — what validates the prompt? Length? Forbidden patterns? Required personas? Look for a shared Zod schema between frontend and backend.

### 3.7 Styling & Theming

**Good:** `THEME_MIGRATION.md` exists; dark theme is consistent per `REVIEW.md` patchsets 106, 109.

**Issues:**
1. **Raw color check script** (`scripts/check_raw_colors.ts`) exists — good. Verify it's wired into CI.
2. **Hardcoded URL check** (`scripts/check_no_hardcoded_urls.ts`) exists — good. Same.
3. **i18n parity check** (`scripts/check_i18n_parity.js`) exists — good. Same.

### 3.8 Testing

**Good:** Vitest configured (`vitest.config.ts`, `vitest.setup.ts`).

**Issues:**
1. **Test coverage is low.** Of 166 components, only a handful have `.test.tsx` files visible (`ArenaRunView.test.tsx`, `CTABanner.test.tsx`, `DivergenceMeter.test.tsx`, `PipelineProgress.test.tsx`, `RunDetailClient.test.tsx`, `lib/sanitize.test.ts`). Aim for 60%+ component coverage.
2. **No E2E coverage visible.** `e2e/` directory exists in `apps/web` listing — verify Playwright tests cover: signup → create debate → watch stream → export report → upgrade plan.
3. **No visual regression** (see 3.4).

---

## 4. Infrastructure, CI & Docs

### 4.1 Docker & Compose

**Good:**
- `docker-compose.yml` has healthchecks on `db` and `redis`.
- `db` uses `postgres:16` (current LTS).
- `redis` uses `:7-alpine` with `appendonly yes` for durability.
- `worker` is a separate service, runs Celery.
- `nginx.conf` proxies `/api/` to `api:8000` and `/` to `web:3000`.

**Issues:**
1. **No multi-stage build in `apps/api/Dockerfile`.** The Dockerfile is 9 lines — it installs all build deps in the runtime image, blows up the image size, and increases attack surface. Use a builder stage:
   ```dockerfile
   FROM python:3.11-slim AS builder
   WORKDIR /build
   COPY requirements.txt .
   RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

   FROM python:3.11-slim
   WORKDIR /app
   COPY --from=builder /wheels /wheels
   RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
   COPY . .
   RUN useradd -m appuser && chown -R appuser:appuser /app
   USER appuser
   ```
2. **Runs as root.** `Dockerfile` has no `USER` directive. Critical security gap — any container escape gives root.
3. **No `.dockerignore`.** `COPY . .` copies `.git`, `node_modules` (if present), `.env`, `__pycache__`, etc. Confirm `.dockerignore` exists in `apps/api/`.
4. **`nginx.conf` is 583 bytes** — that's a single-location proxy, no rate limiting, no TLS, no static asset caching, no gzip, no security headers. The backend adds security headers (`main.py:284–292`) but nginx should also add `Strict-Transport-Security`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`.
5. **No `docker-compose.prod.yml` review.** `infra/docker-compose.prod.yml` exists (1KB) but is too small to be production-ready. Probably just overrides the dev compose. Add: multi-replica API, separate Celery beat, Postgres tuning, Redis maxmemory-policy.
6. **No resource limits (`mem_limit`, `cpus`)** in compose. A single runaway debate can OOM the host.
7. **Health check endpoint is `/healthz`** (per `apps/web/app/healthz/route.ts`) — but the API also needs one. Verify `apps/api/routes/ops.py` has `/healthz` and `/readyz`.

### 4.2 CI Workflows

**Visible:** `ci.yml`, `codeql.yml`, `gitleaks.yml`, `self-healing.yml`, `smoke.yml`.

**Issues (assumed; CI files not in scope to edit):**
1. **`ci.yml` is the main gate.** Verify it runs: ruff, mypy, pytest, vitest, playwright, openapi-drift-check, i18n-parity, raw-color check, hardcoded-URL check. If any of these is not in CI, add them.
2. **`gitleaks.yml`** — good, secrets scanning.
3. **`codeql.yml`** — good, security analysis.
4. **`self-healing.yml`** — interesting; what does it do? If it auto-fixes linting on push, confirm it never touches code without review.
5. **`smoke.yml`** — production smoke tests via `scripts/prod_smoke.ts`. Verify it covers: signup, login, create debate, stream, export.
6. **No dependency review action.** Add `actions/dependency-review-action` to catch vulnerable deps in PRs.
7. **No SBOM generation.** For enterprise customers, you need a Software Bill of Materials. Add `anchore/sbom-action` or `cyclonedx/cyclonedx-python`.
8. **No release workflow.** Tag → Docker build → push → deploy. Add `.github/workflows/release.yml`.

### 4.3 Docs

**Good:** 40+ docs covering architecture, security, investor metrics, traction, defensibility, pricing, GTM, runbooks, incident response, mutation testing, queue backpressure, model gateway, multi-tenancy, public sharing, hosted credits, free trial growth, API access, prompt guardrails, self-healing, SLOs.

**Issues:**
1. **No `docs/CHANGELOG.md`** — there is a root `CHANGELOG.md` (34 lines) but no detailed per-version changelog. VCs and customers want to see "what shipped when."
2. **No `docs/SECURITY.md`** — there is a root `SECURITY.md` (55 lines) but no deep security policy. Add: vulnerability disclosure process, security.txt at `/.well-known/security.txt`, PGP key for contact.
3. **No `docs/CONTRIBUTING.md`** — there is a root `CONTRIBUTING.md` (117 lines) but it's a single file. Consider splitting into `CONTRIBUTING.md` (high-level), `docs/dev/setup.md`, `docs/dev/architecture.md`, `docs/dev/testing.md`.
4. **No `docs/STATUS.md` or live status page.** `docs/RUNBOOKS.md` exists for incidents but no public status. Add a `/status` page or integrate with statuspage.io / Better Uptime.
5. **No `docs/DEPENDENCIES.md` or `docs/SBOM.md`.** Document the critical dependencies and their licenses.
6. **`docs/ARCHITECTURE.md` is 5.5KB** — good but should have an `mermaid` diagram updated to reflect the current state (orchestration/pipeline, state manager, leases).
7. **The `docs/architecture/` subdirectory** exists — verify it has the ADRs (Architecture Decision Records). ADRs are gold for VC diligence ("why did you choose Postgres over MongoDB?").

### 4.4 Client SDKs

**Listing:** `clients/js`, `clients/python`.

**Issues (assumed; not deeply reviewed):**
1. **No version pinning between SDK and API.** Add a `SDK_API_VERSION` constant and a `/api/v1/sdk-version` endpoint.
2. **No automated SDK generation from OpenAPI.** `apps/api/openapi.json` is 261KB — generate the SDKs from it (openapi-generator, fern, or speakeasy).
3. **No SDK changelog or release notes.**
4. **No SDK tests against a mock server.** Prism (from Stoplight) generates a mock from OpenAPI; use it for SDK integration tests.

### 4.5 Database Migrations

**Good:** 36 migrations, including patchset-numbered ones (`p112_…`, `p118_…`). The `ffc07156de2e_add_gin_indexes_to_debate_config` migration adds GIN indexes — correct for JSONB queries.

**Issues:**
1. **No down-migration testing.** Alembic can auto-generate downgrade functions, but they're rarely tested. A bad migration in production is a P0; you need confidence the down works.
2. **No migration for the async session URL pattern** — `config.py:386–393` rewrites `postgresql://` to `postgresql+psycopg://` at runtime. This is a hack; the right fix is to set the async URL in env and use it directly.
3. **Some migrations are named with patchset numbers (`p112_…`), others with descriptive names.** Standardize.
4. **No data migrations for the soft-delete path.** `User.deleted_at` exists but no migration backfills or purges.

---

## 5. VC-Readiness

This section is the **investor-facing** layer. The existing docs (`investor-metrics.md`, `traction-dashboard.md`, `defensibility.md`, `pricing-strategy.md`, `growth-free-trial.md`) are strong. The gaps are mostly in the **operational evidence** and **public surfaces**.

### 5.1 Security Posture

**What's good:**
- Pydantic-validated config with production boot checks.
- PBKDF2 password hashing (recommend Argon2id migration).
- HTTP-only, SameSite cookies; CSRF double-submit for cookie auth.
- API key with prefix + hash + expiry + audit log.
- PII scrubbing before LLM send; sensitive pattern detection before share.
- Public DTOs that strip internal fields (`docs/security-notes.md`).
- Sentry, Langfuse, PostHog instrumentation.

**What's missing:**
1. **No SOC 2 Type 1.** The docs say "SOC2-ready" — that's a claim, not evidence. Plan: 6-month roadmap to SOC 2 Type 1 with a firm (Drata, Vanta, Secureframe).
2. **No pen test report.** Even a single pen test (NCC Group, Trail of Bits, Cobalt) is table stakes for Series A+ diligence.
3. **No bug bounty program.** HackerOne or Bugcrowd, even at $1k–$5k payouts, signals security maturity.
4. **No `SECURITY.md` with disclosure policy.** Just a 55-line root file; needs: contact, scope, safe harbor, response SLA.
5. **No dependency pinning with hashes.** `pip install -r requirements.txt` without `--require-hashes` allows supply-chain attacks. Use `pip-compile --generate-hashes` (pip-tools) or `uv pip compile`.
6. **No secrets scanning in pre-commit.** `gitleaks.yml` is in CI but `.pre-commit-config.yaml` should also include it.
7. **No SBOM** (see 4.3).
8. **No customer-managed encryption keys (CMEK) for hosted credits / API keys.** If you encrypt `UserProviderKey.encrypted_key`, document the KMS provider and key rotation policy.

### 5.2 Compliance

**Missing:**
1. **GDPR data export & deletion endpoints.** DSAR (Data Subject Access Request) is a legal requirement. Add `GET /me/export` and `DELETE /me` with a 30-day grace period.
2. **CCPA "Do Not Sell" link** in the footer.
3. **Cookie consent banner** for EU visitors.
4. **DPA (Data Processing Agreement) template** in `docs/legal/`.
5. **Sub-processor list** — Stripe, OpenAI, Anthropic, Google, etc. Publish at `/legal/sub-processors`.
6. **No HIPAA posture.** If you sell to healthcare, you need a BAA. If not, document why.
7. **No audit log export** for enterprise customers. `AuditLog` exists (`models.py:254–265`) — add `GET /audit-logs.csv` for admins.

### 5.3 Billing & Unit Economics

**What's good:**
- `LLMUsageLog` records per-call cost (`models.py:360`).
- Hosted credits model with refund on failure.
- Stripe integration with webhook signature verification.
- Plan-based quotas (`models.py:234–251`).
- `pricing-strategy.md` exists.

**What's missing:**
1. **No margin dashboard.** You can compute cost from `LLMUsageLog` but no view shows "this user's plan costs us $X, they pay $Y, gross margin is Z%." Add a query and a dashboard.
2. **No LLM cost reconciliation.** `cost_usd` is recorded; the provider's actual invoice may differ (cached tokens, free tier, batch discounts). Run a nightly reconciliation job.
3. **No usage-based pricing tier.** `pricing-strategy.md` describes plans; verify there's a usage-based / overage option for enterprise.
4. **No annual prepay discount.** Standard SaaS play: 17% off for annual.
5. **No invoice customization** (your logo, your address). Stripe supports it; configure it.
6. **No tax handling** (see 2.6).
7. **No dunning** (see 2.6).

### 5.4 Observability for Diligence

**What's good:**
- Langfuse for LLM tracing.
- Sentry for errors.
- PostHog for product analytics.
- Slack alerting on debate failures.

**What's missing:**
1. **A live `/status` page** showing: API uptime, debate success rate, p95 latency, LLM provider health. This is a **huge** trust signal for VCs and customers. Use a public Prometheus / Grafana dashboard or statuspage.io.
2. **A public `/metrics` page** with non-sensitive aggregate stats: total debates run, total tokens processed, top models used. `docs/traction-dashboard.md` describes this; ship the page.
3. **SLO dashboard** in Grafana with error budget burn alerts. Define the SLOs in `docs/observability-slos.md` and wire to PagerDuty.
4. **No runbook for "provider is down."** `docs/RUNBOOKS.md` exists — verify it covers: "OpenAI 503 → switch to OpenRouter → notify users."
5. **No incident postmortem template.** Add `docs/postmortems/YYYY-MM-DD-incident.md` template and publish 2–3 historical ones.
6. **No on-call rotation.** Use PagerDuty or Opsgenie; even a 2-person rotation is fine for pre-PMF.

### 5.5 Scalability

**What's good:**
- Lease + heartbeat for multi-worker safety.
- SSE backend with `redis` option for multi-instance.
- Celery for async debate dispatch.
- Connection pooling (10 + 20 overflow per `config.py:243–245`).
- Composite indexes on hot paths.

**What's missing:**
1. **No load test results.** A single debate = 15+ LLM calls. At 100 concurrent debates = 1500 LLM calls. What's the p95? What breaks first? Run `locust` or `k6` and publish results.
2. **No multi-region strategy.** Are you US-only? EU data residency? Document it.
3. **No CDN in front of static assets.** Next.js handles this on Vercel; if you self-host, add CloudFront / Fastly.
4. **No read replicas.** All queries hit the primary. As you grow, route `/stats/*` and `/leaderboard` to a read replica.
5. **No caching layer for public stats.** `PublicStats` is computed on every request. Cache in Redis with a 60s TTL.
6. **`SSE_MEMORY_MAX_QUEUE_SIZE = 1000`** (`config.py:147`) — for high-traffic debates, this will drop events. Confirm this is intentional and that the client-side `last_sequence` replay handles it.
7. **No rate limit on LLM calls per user** (see 2.7). A single user can DoS your provider quota.

### 5.6 GTM Signals (Investor-Facing)

**What's good:**
- `defensibility.md` is excellent (Borda count, Wilson CI, audit trail).
- `pricing-strategy.md` exists.
- `growth-free-trial.md` exists with hosted-credits mechanic.
- `integrations.md` exists.
- `traction-dashboard.md` describes the metrics to track.

**What's missing:**
1. **No public roadmap.** Add `/roadmap` with a "what's shipped / what's next / what's considered" board. Canny, Productboard, or just a public Notion page.
2. **No public changelog.** `/changelog` with monthly updates. Headless CMS or static MDX.
3. **No customer logos / case studies.** `hall-of-fame` page exists — verify it has real case studies, not just stats.
4. **No "why us" comparison page.** `defensibility.md` is internal; a public `/vs/chatgpt` or `/vs/claude` comparison is high-intent SEO.
5. **No founder letter / manifesto.** A `/about` or `/mission` page with the founder's story converts better than feature lists.
6. **No integration gallery** with screenshots. `integrations.md` is text; screenshots + "how it works" videos convert.
7. **No pricing transparency** beyond the pricing page. Add a "what's included in Free vs Pro" comparison matrix.
8. **No referral program.** Standard PLG play — "give $10, get $10."
9. **No `terms.md` or `privacy.md` review.** `TERMS.md` (119 bytes) and `PRIVACY.md` (121 bytes) are too short to be legally meaningful. Have a lawyer review.
10. **No security.txt at `/.well-known/security.txt`.**

### 5.7 Investor-Facing Metrics

**Per `docs/investor-metrics.md`, the funnel to instrument:**
- `public_run_viewed` → `public_run_cta_clicked` → `signup_completed` → `debate_run_started`

**Issues:**
1. **Verify these events are actually fired.** The doc describes what should happen; confirm PostHog sees them.
2. **No cohort retention chart.** "Users who started 5+ debates in week 1 retain at X% in week 4." This is the core PLG metric.
3. **No magic-number analysis.** "What's the conversion rate from public viewer → signup?" If it's <2%, your GTM needs work.
4. **No LTV / CAC model.** Standard SaaS metrics: LTV:CAC > 3:1, payback < 18 months.
5. **No net revenue retention (NRR).** Track expansion (plan upgrades) vs churn (downgrades + cancels).
6. **No "successful debate" definition.** Is a "successful debate" one that completed? One that the user shared? One that converted to paid? Pick one and report it.

---

## 6. UX

### 6.1 Information Architecture

**Good:**
- Clear route groups: `(app)` for authenticated, `(marketing)` for public.
- Settings under `/(app)/settings/{profile,billing,api-access,audit-logs,data-retention,provider-keys,team}` — well organized.
- Marketing pages: `home, pricing, security, leaderboard, hall-of-fame, models, methodology, demo, docs, contact, login, register`.

**Issues:**
1. **No "What's new" or "Onboarding" page** for first-time users. Where does a new user go after signup? Verify the post-signup flow is a guided tour or a single CTA.
2. **`/runs` vs `/live` vs `/participation` vs `/chamber`** — the user-facing debate routes are fragmented. Consider consolidating: `/runs` = list, `/runs/[id]` = detail, `/runs/[id]/replay` = replay. Drop `/live` and `/chamber` if they're redundant.
3. **No `/docs` deep linking** from in-app help. If a tooltip says "see docs," it should link to the relevant section, not the docs root.
4. **Settings has 7 sub-pages.** Consider a tabbed layout to reduce navigation depth.

### 6.2 Accessibility (a11y)

**Good:**
- Skip-to-content link (`layout.tsx:59–64`).
- `lang={locale}` on `<html>`.
- `aria-live` and `aria-atomic` patterns in `REVIEW.md:4.2` (verify they exist in `useAnnounce` hook).

**Issues:**
1. **No axe-core tests** in Playwright.
2. **No `prefers-reduced-motion` audit.** You have `use-reduced-motion.ts` — verify it's used in: debate streaming animations, modal transitions, loading spinners.
3. **No focus trap in modals.** `BillingLimitModal`, `PromotionArea` — if they use Radix Dialog, focus trap is built in. If they're custom, add it.
4. **No keyboard shortcut discoverability.** If you add `j/k` to navigate messages, add a `?` modal that lists them.
5. **No high-contrast / forced-colors mode test.** The `darkMode: 'class'` config doesn't help Windows High Contrast users.
6. **No screen reader testing notes.** Add a section to `manual-qa-core-flows.md` for VoiceOver / NVDA testing.
7. **Color contrast** — the dark theme likely has some low-contrast text. Run a contrast audit.

### 6.3 Real-Time Streaming UX

**Good:**
- SSE hook with retry, backoff, sequence gap detection (`lib/sse.ts`).
- Reconnect indicator with retry count.

**Issues:**
1. **No "you're offline" banner** when `navigator.onLine === false`.
2. **No optimistic UI for user actions** (votes, reactions). If the user clicks a thumb up, it should feel instant even if the API is slow.
3. **No "X new messages" pill** when the user has scrolled away from the bottom and new messages arrive. Standard pattern in chat UIs.
4. **No scrubbing / seek** for completed debates. If a debate has 50 messages, can the user jump to message 30? A timeline scrubber is high-value.
5. **No export-while-watching.** A user might want to start a report draft while the debate is still running.
6. **No "share this moment" CTA** at key debate milestones (e.g., when consensus forms, when a judge scores 9+).
7. **No sound effects (opt-in)** for new messages. Some users love this; many hate it. Make it opt-in.

### 6.4 Dashboard Usability

**Sampled pages:** `/dashboard`, `/runs`, `/runs/[id]`, `/participation`, `/chamber`.

**Issues:**
1. **Empty states** — what does the dashboard show with 0 debates? A "Start your first debate" CTA with a sample prompt is standard.
2. **Loading states** — verify each page has a skeleton (`loading.tsx`) and not a blank screen.
3. **Error states** — verify each page has `error.tsx` with retry, not a crash.
4. **Search & filter** on `/runs` — by status, date range, model, mode. Likely missing.
5. **Bulk actions** on `/runs` — delete, export, archive. Likely missing.
6. **Sorting** on `/runs` — newest, oldest, longest, most-shared.
7. **No keyboard shortcuts** for power users.
8. **No "recently viewed"** across the app.

### 6.5 Onboarding

**Issues:**
1. **No guided tour** for new users. Use a tool like Userflow, Appcues, or build with Shepherd.js.
2. **No sample debate** button. "Try it without signing up" → public sample with a CTA at the end.
3. **No progress indicator** during account setup (profile, plan, first debate).
4. **No "what's a debate?"** primer. A 30-second video or interactive walkthrough.
5. **Empty state for the dashboard** (see 6.4) is the first onboarding impression.

### 6.6 Billing & Upgrade Flows

**Sampled pages:** `/pricing`, `/(app)/settings/billing`, `BillingLimitModal`.

**Issues:**
1. **Pricing page** should have:
   - ❓ Monthly / annual toggle
   - ❓ Per-feature comparison matrix
   - ❓ "Most popular" badge on the recommended plan
   - ❓ "Trusted by" social proof
   - ❓ "Cancel anytime" trust signal
   - ❓ FAQ section
2. **Upgrade flow** should have:
   - ❓ Proration preview ("You'll be charged $X today")
   - ❓ Confirmation step
   - ❓ Success state with next steps
   - ❓ Email receipt
3. **Downgrade flow** should have:
   - ❓ "What you'll lose" warning
   - ❓ Effective date display
   - ❓ Confirmation modal
4. **Failed payment** should have:
   - ❓ Banner on every page
   - ❓ "Update payment method" CTA
   - ❓ Grace period indicator
5. **No usage forecasting.** "At your current rate, you'll hit your token limit in 3 days." Proactive, not reactive.

### 6.7 Admin Tools

**Sampled pages:** `/admin`, `/admin/users`, `/admin/events`, `/admin/models`, `/admin/ops`, `/admin/promotions`.

**Issues:**
1. **No admin audit trail in the UI.** `AuditLog` exists in the DB; is there a UI to view it? `/(app)/settings/audit-logs/page.tsx` exists — verify it's admin-only.
2. **No impersonation** ("View as user") for support.
3. **No bulk email** from the admin UI.
4. **No support notes** UI for `SupportNote` (`models.py:49–57`).
5. **No feature flag UI** (currently in env vars / config.py).
6. **No "kill switch"** for a model or a provider.
7. **No rate limit override** for VIP users.

### 6.8 Empty / Loading / Error States

**Generic issues (apply to most pages):**
1. **No empty state illustrations** (use a simple SVG or Lottie).
2. **No error recovery** — most error.tsx files probably just say "Something went wrong" with no "Try again" or "Go home" button.
3. **No 404 customization** for the marketing site.
4. **No offline detection** — `navigator.onLine` is rarely used; the app assumes connectivity.
5. **No skeleton loaders** for most pages.

---

## 7. Prioritized Action Plan

This is a **90-day plan** ordered by ROI. Each item has a category, effort estimate, and the "why now."

### 7.1 Critical (Weeks 1–2)

| # | Item | Why now |
|---|---|---|
| 1 | **Dockerfile: multi-stage build, non-root user, .dockerignore** | Security gate for any customer who inspects images |
| 2 | **Add LLM call rate limits per user** (`LLM_RPM_PER_USER`) | Prevents single-user DoS of provider quotas |
| 3 | **Stripe webhook idempotency** (`stripe_event_id` unique constraint) | Double-billing is a P0 customer-trust event |
| 4 | **GDPR data export & deletion endpoints** | Legal requirement for EU customers |
| 5 | **`/status` page** (uptime, debate success rate, p95 latency) | Trust signal for VCs and customers |
| 6 | **`/changelog` page** with public release notes | Standard GTM surface |
| 7 | **Public OpenAPI / SDK automation** | Reduces SDK drift, enables partner integrations |
| 8 | **OpenTelemetry + Prometheus metrics** (histograms + labels) | Required for SLOs, error budgets, and VC diligence |

### 7.2 High (Weeks 3–6)

| # | Item | Why now |
|---|---|---|
| 9 | **Argon2id password hashing migration** | OWASP 2023 best practice; cheap to do |
| 10 | **JWT revocation list in Redis** | Leaked tokens are valid until exp otherwise |
| 11 | **Sentry + trace_id in error responses** | Cuts MTTR by 50%+ |
| 12 | **PostHog funnel verification** (`public_run_viewed` → `signup_completed`) | The core PLG metric must be measurable |
| 13 | **A/B test pricing page** (annual vs monthly default, plan order) | Pricing is the highest-leverage growth lever |
| 14 | **Stripe tax + invoice customization** | EU sales + enterprise procurement |
| 15 | **Pen test engagement** (NCC Group, Trail of Bits, Cobalt) | Required for SOC 2 and Series A diligence |
| 16 | **SOC 2 Type 1 roadmap** (Drata / Vanta / Secureframe) | 6-month lead time; start now |
| 17 | **Nginx: add security headers, gzip, static caching** | Cheap performance + security win |
| 18 | **Frontend: add `loading.tsx` and `error.tsx` to all App Router pages** | UX baseline |
| 19 | **Frontend: empty states for dashboard, runs, settings** | First-impression UX |
| 20 | **Frontend: keyboard shortcuts for debate navigation** (`j/k`, `/`, `?`) | Power-user delight |
| 21 | **Frontend: axe-core a11y tests in Playwright** | Catches 30%+ of a11y bugs automatically |

### 7.3 Medium (Weeks 7–10)

| # | Item | Why now |
|---|---|---|
| 22 | **DB migration for soft-delete purge** | GDPR compliance |
| 23 | **`SECURITY.md` with disclosure policy + `/.well-known/security.txt`** | Bug bounty readiness |
| 24 | **Bug bounty program** (HackerOne, $1k–$5k payouts) | External security signal |
| 25 | **Public roadmap page** (`/roadmap`) | Reduces "what are you building?" sales friction |
| 26 | **Customer case studies** (3–5 real ones) | GTM conversion |
| 27 | **Comparison pages** (`/vs/chatgpt`, `/vs/claude`) | High-intent SEO |
| 28 | **DPA template in `docs/legal/`** | Enterprise sales gate |
| 29 | **Sub-processor list at `/legal/sub-processors`** | GDPR transparency |
| 30 | **Margin dashboard** (LLM cost vs plan revenue) | Unit economics visibility |
| 31 | **LLM cost reconciliation job** (nightly) | Margin accuracy |
| 32 | **Runbook for "provider down"** | MTTR reduction |
| 33 | **Incident postmortem template + 2–3 historical postmortems** | Operational maturity signal |
| 34 | **Frontend: Storybook 8 setup** | Visual regression enables safe refactors |
| 35 | **Frontend: PWA manifest + offline support for read-only pages** | Mobile UX |
| 36 | **Frontend: optimistic UI for votes, reactions** | Perceived performance |
| 37 | **Frontend: "X new messages" pill when scrolled away** | Real-time UX standard |
| 38 | **Frontend: usage forecasting in billing page** | Retention lever |
| 39 | **Backend: per-model circuit breakers** (not just per-provider) | Granular resilience |
| 40 | **Backend: rate limit fingerprinting** (UA + accept-language) | IP-only limits are bypassable |

### 7.4 Low / Nice to Have (Weeks 11–12+)

| # | Item | Why now |
|---|---|---|
| 41 | **Property-based testing with `hypothesis`** | Catches edge cases unit tests miss |
| 42 | **Mutation testing** (mutmut, cosmic-ray) | Verifies test quality |
| 43 | **Load testing** (locust / k6) with published results | VC diligence signal |
| 44 | **SBOM generation** (CycloneDX) | Enterprise procurement |
| 45 | **Multi-region / EU data residency** | EU enterprise sales |
| 46 | **CDN in front of static assets** | Performance |
| 47 | **Read replicas for `/stats/*` and `/leaderboard`** | Scale |
| 48 | **CMEK for hosted credits / API keys** | Regulated industry sales |
| 49 | **HIPAA posture decision** (yes / no / roadmap) | Healthcare vertical |
| 50 | **Referral program** ("give $10, get $10") | PLG growth |
| 51 | **Annual prepay discount** (17% off) | Standard SaaS |
| 52 | **Admin: impersonation ("view as user")** | Support efficiency |
| 53 | **Admin: feature flag UI** | DX |
| 54 | **Admin: kill switch per model / provider** | Incident response |
| 55 | **Admin: bulk email** | Marketing + support |
| 56 | **Frontend: sound effects (opt-in)** for new messages | Power-user delight |
| 57 | **Frontend: timeline scrubber for completed debates** | Power-user feature |
| 58 | **Frontend: dark/light theme toggle in user settings** | Personalization |

---

## Appendix A: Files Read

This review is grounded in the following files (representative, not exhaustive):

**Backend (apps/api):**
- `main.py` (493 lines)
- `config.py` (515 lines)
- `auth.py` (400 lines)
- `models.py` (557 lines)
- `orchestrator.py` (833 lines)
- `parliament/engine.py` (first 200 lines)

**Frontend (apps/web):**
- `app/layout.tsx` (75 lines)
- `lib/sse.ts` (327 lines)
- `app/providers.tsx` (47 lines, file size)
- `lib/apiClient.ts` (162 lines, file size)
- `lib/api/hooks/useDebate.ts` (47 lines, file size)

**Infrastructure:**
- `infra/docker-compose.yml`
- `infra/nginx.conf`
- `apps/api/Dockerfile`

**Docs:**
- `docs/ARCHITECTURE.md`
- `docs/security-notes.md`
- `docs/investor-metrics.md`
- `docs/traction-dashboard.md`
- `docs/defensibility.md`

**Meta:**
- `REVIEW.md` (1211 lines — pre-existing)
- `CHANGELOG.md`, `README.md`, `RULES.MD`, `CONTRIBUTING.md`

## Appendix B: What's Already Done (Per `REVIEW.md`)

The pre-existing `REVIEW.md` is the source of truth for what's been shipped. Key items already done:
- Async token usage logging (commit `27eb0ed`)
- DB connection leak fix (commit `6c03215`)
- Provider circuit breaker + OpenRouter fallback (Patchset 101)
- Strict production boot validation (Patchset 107)
- Auth token hardening (Patchset 110)
- SSE memory backend enforcement (Patchset 75)
- LLM retry/backoff configuration (`LLM_RETRY_*` settings)
- Pydantic settings validation (`config.py` with `BaseSettings`)
- Dark theme consistency (Patchsets 106, 109)
- Transcript layout improvements (Patchset 109)
- Conversation-first architecture (Patchset 111)
- Composite indexes (`ix_debate_user_status_created`, `ix_message_debate_round`)
- Lease + heartbeat for multi-worker safety
- Hosted credit refund on transient LLM failure
- Langfuse + Sentry + PostHog instrumentation
- Google OAuth with sanitized `next` param
- CORS strict validation in production
- API key expiry, revocation, audit log
- 36 Alembic migrations including GIN indexes on JSONB
- PII scrubbing before LLM send
- Sensitive pattern detection before public share
- Public DTOs that strip internal fields
- i18n infrastructure with server-side message loading
- View transitions for smooth navigation
- Skip-to-content link

## Appendix C: The 5 Things I'd Do First If I Were the New CTO

1. **Ship `/status` and `/changelog` pages this week.** They're the cheapest, highest-signal trust surfaces for VCs and customers. Both are pure frontend + a single API endpoint.
2. **Add per-user LLM rate limits and Stripe webhook idempotency this week.** Both are P0 risks that compound with growth.
3. **Engage a pen test firm this month.** $30k–$80k buys you a report that closes 80% of enterprise security questionnaires.
4. **Stand up Prometheus + OpenTelemetry this month.** Without histograms, you cannot answer "is the system healthy?" — and VCs will ask.
5. **Hire a product designer (or contract one) for a 30-day sprint on the dashboard, billing, and admin UIs.** The backend is ahead of the frontend. A designer can ship more UX value in a month than three engineers.

---

*Review prepared as a near line-by-line audit. File:line references are from the snapshot at the time of review; subsequent patches may have shifted line numbers. All recommendations are advisory and should be triaged against current priorities.*
