# Consultaion — Full Implementation Walkthrough

> **Generated:** 2026-06-14
> **Branch:** `main`
> **Commits:** `c4b257f` · `b1a91bc` · (current uncommitted session)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Master Patchset (PR-1 through PR-13)](#master-patchset)
3. [Operational Trust Addendum (PR-OT1 through PR-OT11)](#operational-trust-addendum)
4. [File Map](#file-map)
5. [How to Run](#how-to-run)
6. [Feature Flags](#feature-flags)
7. [Testing](#testing)
8. [Deployment](#deployment)

---

## Architecture Overview

```
Consultaion
├── apps/
│   ├── api/                    # Python/FastAPI backend
│   │   ├── main.py             # App entrypoint, middleware, router registration
│   │   ├── config.py           # Pydantic settings (530 lines)
│   │   ├── auth.py             # JWT, API keys, CSRF, stream tokens
│   │   ├── database.py         # SQLAlchemy engine, session, init
│   │   ├── ratelimit.py        # Redis/memory rate limiter backends
│   │   ├── metrics.py          # In-process metric counters
│   │   ├── exception_handlers.py  # Standardized error envelope
│   │   ├── core/
│   │   │   ├── operation_classes.py  # OperationClass enum + weights
│   │   │   └── router_registry.py    # Centralized router registration
│   │   ├── middleware/
│   │   │   ├── body_limit.py         # 10MB request body limit
│   │   │   └── weighted_rate_limit.py # Cost-unit rate limiting
│   │   ├── observability/
│   │   │   ├── metrics.py      # Prometheus counters/histograms/gauges
│   │   │   ├── tracing.py      # OpenTelemetry distributed tracing
│   │   │   └── slo.py          # SLO definitions + budget tracking
│   │   ├── billing/
│   │   │   ├── routes.py       # Billing API + Stripe webhooks
│   │   │   ├── service.py      # Quota checks, credit management
│   │   │   ├── reconciliation.py # Cost reconciliation job
│   │   │   └── providers/      # Stripe provider
│   │   ├── gdpr/
│   │   │   ├── routes.py       # Export + deletion endpoints
│   │   │   └── service.py      # GDPR business logic
│   │   ├── integrations/
│   │   │   └── posthog.py      # Backend analytics
│   │   ├── routes/             # 25+ domain routers
│   │   └── requirements.txt    # Pinned dependencies
│   └── web/                    # Next.js App Router frontend
│       ├── app/(app)/          # Authenticated routes
│       ├── app/(marketing)/    # Public pages
│       ├── components/
│       │   ├── workspace/      # WorkspaceHeader, MobileStageBar, etc.
│       │   ├── arena/          # ModelPanelSheet, ArenaRunView, etc.
│       │   ├── prompt/         # IdleDecisionComposer, ActiveWorkspaceComposer
│       │   ├── report/         # ReportSection (scroll-spy)
│       │   ├── consultaion/    # DashboardShell (sidebar a11y)
│       │   └── ui/             # Toast, ErrorBoundary, EmptyState
│       ├── hooks/              # useRunWorkspace, useOnlineStatus, etc.
│       ├── lib/
│       │   ├── api/types.ts    # DTOs, SSE event types
│       │   ├── workspace/      # types.ts, deriveWorkspaceStage.ts
│       │   ├── feature-flags.ts
│       │   ├── motion.ts
│       │   └── analytics.ts    # Frontend PostHog
│       ├── e2e/                # Playwright E2E + axe-core
│       └── Dockerfile          # Multi-stage, non-root
├── .github/workflows/
│   ├── ci.yml                 # Full CI pipeline
│   ├── release.yml            # Docker + GitHub Release
│   ├── gitleaks.yml           # Secret scanning
│   └── codeql.yml             # CodeQL analysis
└── opencode.json              # Agent permissions
```

---

## Master Patchset

### PR-1: Backend Continuation Correctness
**Files:** `routes/debates.py`, `debate_dispatch.py`, `orchestrator.py`, `orchestrator_cleanup.py`, `billing/service.py`

- `resume=True` dispatch for staged pipeline resumption
- `DebateContinuation` model: requested → preflight_passed → dispatched → running → completed/failed
- Atomic SQL transitions: `UPDATE debate WHERE status IN ('perspectives_ready','failed')`
- Credit reservation/refund/consume lifecycle in `billing/service.py`
- Worker lifecycle: max_retries=3, lease/heartbeat system, stale cleanup loop

### PR-2: Stage Checkpoints & Retry Safety
**Files:** `models.py` (DebateStageCheckpoint), `orchestration/checkpoints.py`, `orchestration/pipeline.py`, `routes/debates.py`

- `DebateStageCheckpoint` model with SHA-256 input hash matching
- `run_with_checkpoint()` wraps each pipeline stage
- Resume from checkpoint: completed stages skipped automatically
- `X-Idempotency-Key` header with unique constraint on `(debate_id, idempotency_key)`
- `DOWNSTREAM_STAGES` map for cascade clearing on retry

### PR-3: API Contracts & Shared Workspace State
**Files:** `schemas.py`, `lib/api/types.ts`, `lib/workspace/types.ts`, `lib/workspace/deriveWorkspaceStage.ts`

- `DebateSummary` DTO expanded with stage checkpoints
- `StageCheckpointDTO`, `ContinuationDTO` types
- 11 standardized SSE event types (pipeline_stage_started/completed/failed, model_response_*, perspectives_ready, continuation_*, decision_report_ready, verification_completed)
- `WorkspaceStage`, `WorkspaceState`, `WorkspaceModelSlot` types
- `deriveWorkspaceStage()` pure function for workspace state derivation

### PR-4: Unified /live Workspace
**Files:** `components/workspace/WorkspaceHeader.tsx`, `MobileStageBar.tsx`, `DesktopStageRail.tsx`, `PerspectivesGrid.tsx`, `PerspectivesReadyAction.tsx`, `app/(app)/live/page.tsx`

- `WorkspaceHeader`: mode indicator, elapsed timer, controls
- `MobileStageBar`: compact horizontal stage indicator with dots
- `DesktopStageRail`: vertical sidebar with stage details
- `PerspectivesGrid`: responsive model position cards
- `PerspectivesReadyAction`: CTA when perspectives are ready
- Full `/live` route (756 lines) with all components composed

### PR-5: Mobile-First Interaction
**Files:** `components/arena/ModelSearchInput.tsx`, `SelectedModelsTray.tsx`, `ModelListRow.tsx`, `components/prompt/IdleDecisionComposer.tsx`, `ActiveWorkspaceComposer.tsx`

- `ModelSearchInput`: debounced search with keyboard navigation
- `SelectedModelsTray`: horizontal scroll of selected models
- `ModelListRow`: full-width touch target with provider badge
- `IdleDecisionComposer`: prompt input for idle state
- `ActiveWorkspaceComposer`: floating composer for active runs

### PR-6: Mobile Model Panel
**Files:** `components/arena/ModelPanelSheet.tsx` (194 lines)

- Single responsive component: 92dvh bottom sheet on mobile, full sidebar on desktop
- Composes `ModelSearchInput`, `SelectedModelsTray`, `ModelListRow`

### PR-8: Mobile Response & Pipeline UX
**Files:** `components/arena/ArenaRunView.tsx`, `components/arena/PipelineProgress.tsx`, `components/ui/toast.tsx`, `hooks/useRunWorkspace.ts`

- Counter text ("1 of 4") + progress dots with active width animation
- `Toast` component: 4 variants, auto-dismiss, `role="alert"`
- `useRunWorkspace`: idempotency key via `crypto.randomUUID()` per mount
- All `alert()` calls replaced with Toast

### PR-9: Mobile Decision Report
**Files:** `components/report/ReportSection.tsx`, `components/parliament/RoundGrid.tsx`

- IntersectionObserver scroll-spy: `rootMargin: "-20% 0px -60% 0px"`
- Report sections: VerdictCard, KeyFindingsGrid, ModelPositionsTable, RiskMatrix, NextActionsList
- Focus Mode with TOC navigation

### PR-10: Mobile App Shell
**Files:** `components/consultaion/consultaion/dashboard-shell.tsx` (715 lines)

- `role="dialog"`, `aria-modal="true"`, `aria-label="Primary navigation"`
- Focus trap (Tab/Shift+Tab cycling)
- Escape close, body scroll lock
- 44×44px minimum touch targets
- Returns focus to trigger element

### PR-11: Accessibility/Performance/Motion
**Files:** `lib/motion.ts`, `hooks/use-reduced-motion.ts`, `app/(app)/runs/[id]/RunDetailClient.tsx`

- `MOTION_FAST=140`, `MOTION_BASE=220`, `MOTION_SLOW=320`
- Global `@media (prefers-reduced-motion: reduce)` CSS
- Lazy-loaded views via `next/dynamic`: DebateArena, ParliamentRunView, CompareRunView, ConversationRunView, ArenaRunView, VotingRunView

### PR-12: Observability
**Files:** `lib/analytics.ts`, `integrations/posthog.py`, `routes/debates.py`

- Frontend: 58+ `trackEvent()` calls across components
- Backend: PostHog `track_event()` wired into `create_debate` and `start_debate_run`
- Events: `workspace_opened`, `mode_selected`, `prompt_started`, `debate_created`, `debate_started`

### PR-13: Feature Flags
**Files:** `lib/feature-flags.ts`, `apps/web/.env.example`, `apps/api/config.py`

- 13 flags: `stagedDecisionPipeline`, `unifiedWorkspace`, `mobileWorkspaceV2`, `jitAuth`, `mobileReportV2`, `llmOperationLimits`, `prometheusMetrics`, `otelTracing`, `gdprSelfService`, `statusPage`, `changelog`, `offlineRecovery`
- `isFeatureEnabled()` utility function

---

## Operational Trust Addendum

### PR-OT1: Container Hardening
**Files:** `apps/api/Dockerfile`, `apps/api/.dockerignore`, `apps/web/Dockerfile`

**API (Python):**
- Multi-stage: builder (build deps) → runtime (minimal)
- Non-root user `consultaion` (UID 1001)
- `HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3`
- `.dockerignore`: 33 exclusions (DBs, logs, test artifacts, alembic versions)

**Frontend (Node):**
- Multi-stage: builder → runtime (standalone output)
- Non-root user `consultaion` (GID/UID 1001)
- `HEALTHCHECK` via wget to `/api/health`
- `next.config.js` output: "standalone" for minimal production image

### PR-OT2: Expensive-Operation Rate Limits
**Files:** `middleware/weighted_rate_limit.py`, `core/operation_classes.py`

- `OperationClass` enum: `LIGHT=1`, `MEDIUM=3`, `HEAVY=8` cost units
- `_classify_endpoint()` maps method+path to action names
- Per-user weighted budget: PROD=200, DEV=800 cost units per 60s window
- Returns `429` with structured error: `operation_class`, `cost_units`, `budget`, `window_seconds`
- Response headers: `X-RateLimit-Budget`, `X-RateLimit-Action`, `X-RateLimit-Cost`

### PR-OT3: Production Configuration
**Files:** `config.py`, `main.py`

- Rejects in production: `FAST_DEBATE=True`, `STRIPE_WEBHOOK_INSECURE_DEV=True`, `USE_MOCK=True`, `REQUIRE_REAL_LLM=False`, `ENABLE_SEC_HEADERS=False`, `ENABLE_CSRF=False`
- `DEPLOY_TARGET`: auto-derived from environment (local/render/docker/ecs/fly/railway/other)
- Startup logging: env, deploy_target, sse_backend, rate_limit_backend, dispatch_mode, cookie_domain, cors_origins

### PR-OT4: API-Key Usage Write Optimization
**Files:** `auth.py`

- Conditional `last_used_at` update: only writes when stale >5 minutes (300 seconds)
- Reduces DB write amplification: 100 requests → at most 1 DB write per 5 minutes

### PR-OT5: Metrics, Tracing, Safe Error References
**Files:** `observability/metrics.py`, `observability/tracing.py`, `observability/slo.py`, `exception_handlers.py`

**Prometheus (`/metrics` endpoint):**
- `consultaion_http_requests_total` (method, path, status)
- `consultaion_http_request_duration_seconds` (histogram, 11 buckets)
- `consultaion_llm_requests_total` (provider, model, operation_class)
- `consultaion_llm_tokens_total` (provider, model, direction)
- `consultaion_debate_runs_total` (mode, status)
- `consultaion_billing_webhooks_total` (provider, event_type, status)
- `consultaion_sse_streams_active` (gauge)
- `consultaion_rate_limit_exceeded_total` (limit_type, backend)
- `consultaion_db_pool_size`, `consultaion_db_pool_checked_out` (gauges)

**OpenTelemetry:**
- `TracerProvider` initialization with `BatchSpanProcessor(ConsoleSpanExporter)`
- `traced_span()` context manager with exception recording
- `record_llm_span()` for inference operations
- All no-ops when `ENABLE_OTEL_TRACING=False`

**SLOs (`/ops/slo` endpoint):**
- `api_availability`: 99.9% (28-day window)
- `llm_inference_latency`: 95% under 30s (7-day window)
- `debate_success_rate`: 98% (7-day window)
- `sse_delivery`: 99% within 5s (7-day window)
- Sliding-window `SLOBudgetTracker` with burn-rate detection

**Error Trace IDs:**
- All 3 exception handlers include `trace_id` from `x-request-id` header or auto-generated `01J{uuid}` format

### PR-OT6: GDPR Export & Deletion
**Files:** `gdpr/routes.py`, `gdpr/service.py`

| Endpoint | Method | Description |
|---|---|---|
| `/gdpr/export` | POST | Export all user data as JSON (profile, billing, audit logs) |
| `/gdpr/export/download/{filename}` | GET | Download exported file (user-scoped security check) |
| `/gdpr/deletion-request` | POST | Request account deletion (30-day grace period) |
| `/gdpr/deletion-cancel` | POST | Cancel pending deletion, reactivate account |
| `/gdpr/deletion-status` | GET | Check deletion request status + days remaining |
| `/gdpr/admin/process-deletions` | POST | Admin: process scheduled deletions (owner only) |

- `_anonymize_user()`: replaces PII with anonymized values, preserves referential integrity
- `GDPR_DELETION_GRACE_DAYS=30` configurable

### PR-OT7: Public Status, Changelog, Security Surfaces
**Files:** `public/.well-known/security.txt`, `app/(marketing)/changelog/page.tsx`, `app/(marketing)/legal/sub-processors/page.tsx`

- `/.well-known/security.txt`: contact, expires, preferred-languages, canonical URL
- `/changelog`: structured entries with category badges (Product, Mobile, Reliability, Security)
- `/legal/sub-processors`: 7 vendors (Stripe, OpenAI, Anthropic, Google, PostHog, Redis, Vercel) with data categories, regions, DPA status

### PR-OT8: Frontend Reliability
**Files:** `hooks/useOnlineStatus.ts`, `app/(app)/live/loading.tsx`, `app/(app)/live/error.tsx`, `app/(app)/settings/loading.tsx`, `app/(app)/settings/error.tsx`

- `useOnlineStatus()` hook: detects offline/online with `navigator.onLine` + event listeners
- Loading skeletons: `/live`, `/settings`, `/runs`, `/runs/[id]`
- Error boundaries: `/live`, `/settings`
- Empty states: `EmptyState` + `EmptyStateModern` components

### PR-OT9: Router Registry
**Files:** `core/router_registry.py`

- `RouterRegistration` dataclass with prefix, tags, dependency info
- `build_router_registry()`: returns ordered list of all router registrations
- `register_routers()`: applies registry to app with middleware injection

### PR-OT10: Billing Transactionality
**Files:** `billing/routes.py`, `billing/reconciliation.py`

**Webhook Atomicity:**
- Stripe webhook handler wrapped in `session_scope()` context manager
- If handler fails midway → entire transaction rolled back → Stripe retries
- `record_billing_webhook()` Prometheus metric on success/error

**Cost Reconciliation:**
- `reconcile_usage()`: compares `BillingUsage` records against expected values
- Checks: negative tokens, negative debates, per-model totals
- `should_run_reconciliation()`: daily at 03:00 UTC, 12-hour dedup
- `record_reconciliation_time()`: Redis-backed timestamp tracking

### PR-OT11: CI Evidence, SBOM, Release
**Files:** `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `requirements.txt`

**CI Pipeline (`ci.yml`):**
- `url-scan`: Hardcoded URL detection
- `i18n-parity`: Internationalization parity check
- `security-scan`: Gitleaks + Bandit SAST + pip-audit + npm audit
- `sbom-generation`: CycloneDX SBOMs for Python + Node (90-day retention)
- `backend-test`: pytest with coverage
- `backend-postgres-test`: Integration tests on PostgreSQL
- `openapi-drift-check`: OpenAPI schema drift detection
- `python-3.12-compatibility`: Non-blocking compatibility check
- `frontend-build`: Next.js production build
- `e2e-test`: Playwright E2E with axe-core accessibility

**Release Workflow (`release.yml`):**
- Triggered on `v*` tags or manual dispatch
- Pre-release SBOM audit (pip-audit + npm audit)
- Docker Buildx with semver tags + SHA tags
- GitHub Release with auto-generated changelog + SBOM artifact

**Hash-Pinned Requirements:**
- All packages pinned with `--hash=sha256:` annotations
- Verifiable via `pip install --require-hashes -r requirements.txt`

---

## File Map

### New Files Created

| File | PR | Purpose |
|---|---|---|
| `apps/api/middleware/weighted_rate_limit.py` | OT-2 | Cost-unit rate limiting |
| `apps/api/core/operation_classes.py` | OT-2 | Operation class enum + weights |
| `apps/api/core/router_registry.py` | OT-9 | Centralized router registration |
| `apps/api/observability/__init__.py` | OT-5 | Observability package |
| `apps/api/observability/metrics.py` | OT-5 | Prometheus metrics |
| `apps/api/observability/tracing.py` | OT-5 | OpenTelemetry tracing |
| `apps/api/observability/slo.py` | OT-5 | SLO definitions + budget tracking |
| `apps/api/gdpr/__init__.py` | OT-6 | GDPR package |
| `apps/api/gdpr/routes.py` | OT-6 | GDPR API endpoints |
| `apps/api/gdpr/service.py` | OT-6 | GDPR business logic |
| `apps/api/billing/reconciliation.py` | OT-10 | Cost reconciliation job |
| `apps/web/lib/workspace/types.ts` | PR-3 | Workspace state types |
| `apps/web/lib/workspace/deriveWorkspaceStage.ts` | PR-3 | Stage derivation logic |
| `apps/web/lib/feature-flags.ts` | PR-13 | Feature flag utility |
| `apps/web/lib/motion.ts` | PR-11 | Motion timing constants |
| `apps/web/hooks/useOnlineStatus.ts` | OT-8 | Offline detection hook |
| `apps/web/components/workspace/WorkspaceHeader.tsx` | PR-4 | Workspace header component |
| `apps/web/components/workspace/MobileStageBar.tsx` | PR-4 | Mobile stage indicator |
| `apps/web/components/workspace/DesktopStageRail.tsx` | PR-4 | Desktop stage sidebar |
| `apps/web/components/workspace/PerspectivesGrid.tsx` | PR-4 | Model position cards |
| `apps/web/components/workspace/PerspectivesReadyAction.tsx` | PR-4 | Perspectives CTA |
| `apps/web/components/workspace/index.ts` | PR-4 | Barrel export |
| `apps/web/components/arena/ModelSearchInput.tsx` | PR-5 | Model search component |
| `apps/web/components/arena/SelectedModelsTray.tsx` | PR-5 | Selected models tray |
| `apps/web/components/arena/ModelListRow.tsx` | PR-5 | Model list row |
| `apps/web/app/(app)/live/loading.tsx` | OT-8 | Live page loading skeleton |
| `apps/web/app/(app)/live/error.tsx` | OT-8 | Live page error boundary |
| `apps/web/app/(app)/settings/loading.tsx` | OT-8 | Settings loading skeleton |
| `apps/web/app/(app)/settings/error.tsx` | OT-8 | Settings error boundary |
| `apps/web/app/(marketing)/changelog/page.tsx` | OT-7 | Changelog page |
| `apps/web/app/(marketing)/legal/sub-processors/page.tsx` | OT-7 | Sub-processors page |
| `apps/web/public/.well-known/security.txt` | OT-7 | Security disclosure |
| `.github/workflows/release.yml` | OT-11 | Release workflow |

### Modified Files

| File | PRs | Changes |
|---|---|---|
| `apps/api/main.py` | OT-2,OT-3,OT-5,OT-6,OT-9 | Middleware, metrics endpoint, SLO endpoint, GDPR router, startup logging |
| `apps/api/config.py` | OT-3,OT-10 | DEPLOY_TARGET, production flag rejection, weighted RL budget, OT feature flags |
| `apps/api/auth.py` | OT-4 | Conditional last_used_at update |
| `apps/api/exception_handlers.py` | OT-5 | trace_id in all error responses |
| `apps/api/ratelimit.py` | — | (unchanged, used by weighted middleware) |
| `apps/api/billing/routes.py` | OT-10 | Webhook atomicity via session_scope(), PostHog metrics |
| `apps/api/requirements.txt` | OT-5,OT-11 | Added prometheus-client, opentelemetry, cyclonedx-bom, hash annotations |
| `apps/api/routes/debates.py` | OT-12 | PostHog tracking on debate creation and start |
| `apps/api/Dockerfile` | OT-1 | Multi-stage, non-root, healthcheck |
| `apps/api/.dockerignore` | OT-1 | 33 exclusions |
| `apps/web/Dockerfile` | OT-1 | Multi-stage, non-root, healthcheck, standalone |
| `apps/web/lib/api/types.ts` | PR-3 | Expanded DTOs, SSE event types |
| `apps/web/lib/api.ts` | PR-3 | continueDebate with idempotency key |
| `apps/web/hooks/useRunWorkspace.ts` | PR-8 | Idempotency key persistence |
| `apps/web/components/arena/ModelPanelSheet.tsx` | PR-6 | Refactored to use extracted components |
| `apps/web/components/arena/ArenaRunView.tsx` | PR-8 | Counter, progress dots, clamped swipe |
| `apps/web/components/report/ReportSection.tsx` | PR-9 | IntersectionObserver scroll-spy |
| `apps/web/components/consultaion/consultaion/dashboard-shell.tsx` | PR-10 | Sidebar accessibility (dialog, focus trap, body lock) |
| `apps/web/app/(app)/runs/[id]/RunDetailClient.tsx` | PR-11 | Lazy-loaded views, Toast errors |
| `apps/web/app/(app)/live/page.tsx` | PR-12 | PostHog events, mode_selected, prompt_started |
| `apps/web/app/(app)/settings/team/page.tsx` | PR-8 | alert→Toast |
| `apps/web/app/(app)/settings/audit-logs/page.tsx` | PR-8 | alert→Toast |
| `apps/web/app/(admin)/quota/page.tsx` | PR-8 | alert→Toast |
| `apps/web/.env.example` | PR-13,OT-6 | 13 feature flags, OT flags |
| `apps/web/e2e/a11y.spec.ts` | OT-8 | Tests for changelog, subprocessors, settings, runs, live |
| `.github/workflows/ci.yml` | OT-11 | SBOM generation job |
| `opencode.json` | — | git push permission changed to allow |

---

## How to Run

### Backend (API)
```bash
cd apps/api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend (Web)
```bash
cd apps/web
npm install
npm run dev
```

### Docker (Production)
```bash
# API
docker build -t consultaion-api -f apps/api/Dockerfile apps/api
docker run -p 8000:8000 consultaion-api

# Web
docker build -t consultaion-web -f apps/web/Dockerfile apps/web
docker run -p 3000:3000 consultaion-web
```

### E2E Tests
```bash
npx playwright install
npx playwright test
```

---

## Feature Flags

All flags default to `0` (disabled) in production.

| Flag | Purpose |
|---|---|
| `STAGED_DECISION_PIPELINE` | Enable staged pipeline UI |
| `NEXT_PUBLIC_UNIFIED_WORKSPACE` | Unified workspace layout |
| `NEXT_PUBLIC_MOBILE_WORKSPACE_V2` | Mobile workspace v2 |
| `NEXT_PUBLIC_JIT_AUTH` | Just-in-time authentication |
| `NEXT_PUBLIC_MOBILE_REPORT_V2` | Mobile report v2 |
| `ENABLE_LLM_OPERATION_LIMITS` | LLM operation class limits |
| `ENABLE_PROMETHEUS_METRICS` | Prometheus /metrics endpoint |
| `ENABLE_OTEL_TRACING` | OpenTelemetry distributed tracing |
| `ENABLE_GDPR_SELF_SERVICE` | GDPR export/deletion endpoints |
| `NEXT_PUBLIC_STATUS_PAGE` | Public status page |
| `NEXT_PUBLIC_CHANGELOG` | Public changelog page |
| `NEXT_PUBLIC_OFFLINE_RECOVERY` | Offline recovery UI |

---

## Testing

### Python (Backend)
```bash
cd apps/api
ENV=test USE_MOCK=1 pytest -q
```

### TypeScript (Frontend)
```bash
cd apps/web
npx tsc --noEmit
npm run lint
```

### Accessibility (axe-core)
```bash
npx playwright test e2e/a11y.spec.ts
```
Tests: landing, demo, login, register, contact, terms, privacy, changelog, sub-processors, settings, runs, live

---

## Deployment

### Environment Variables Required
```bash
# Database
DATABASE_URL=postgresql://...

# Auth
JWT_SECRET=<64-char-random>

# Redis (production)
REDIS_URL=redis://...

# Stripe
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...

# LLM Providers (at least one)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Observability
SENTRY_DSN=https://...
POSTHOG_API_KEY=phc_...
LANGFUSE_PUBLIC_KEY=pk-...

# Frontend
NEXT_PUBLIC_APP_URL=https://app.consultaion.com
NEXT_PUBLIC_WEB_URL=https://consultaion.com
```

### Production Checklist
- [ ] `ENV=production`
- [ ] `JWT_SECRET` set to 64+ char random value
- [ ] `REDIS_URL` configured
- [ ] `STRIPE_WEBHOOK_SECRET` set
- [ ] At least one LLM provider key configured
- [ ] `ENABLE_SEC_HEADERS=True` (default)
- [ ] `ENABLE_CSRF=True` (default)
- [ ] `FAST_DEBATE=False` (default, rejected if True)
- [ ] `STRIPE_WEBHOOK_INSECURE_DEV=False` (default, rejected if True)
- [ ] `SSE_BACKEND=redis` for multi-worker
- [ ] `DEPLOY_TARGET` auto-derived or explicitly set

### Health Endpoints
| Endpoint | Purpose |
|---|---|
| `/health` | Basic health check |
| `/metrics` | Prometheus metrics |
| `/ops/slo` | SLO status + error budget |
| `/api/v1/health` | Namespaced health check |

---

## Commit History

| Hash | Message |
|---|---|
| `c4b257f` | Pre-existing master patchset work |
| `b1a91bc` | Master patchset implementation (PR-1 through PR-13) |
| (uncommitted) | Operational Trust addendum (PR-OT1 through PR-OT11) + gap fixes |

---

*This document was generated as part of the Consultaion Operational Trust hardening initiative.*
