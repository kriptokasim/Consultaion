# Implementation Status — Final Hardening Patchset

This document tracks the implementation status of the Final Hardening patchset (PR-FH19 through PR-FH28).

## Phase 1 — Correctness Blockers

### PR-FH19: Continuation State Machine
- **Status:** Complete
- **Changes:**
  - `ContinuationTransitionError` exception in `exceptions.py`
  - `transition_continuation_sync` / `transition_continuation_async` in `continuations.py`
  - `continuation_id: Optional[str]` in `DebateContext` (interfaces.py)
  - Continuation ID wired through `orchestrator.py`, `debate_dispatch.py`
  - `ContinuationResponse` schema in `schemas.py`
  - POST `/debates/{id}/continue` with idempotency handling
  - GET `/debates/{id}/continuations/{continuation_id}` endpoint
  - `perspectives_ready` no longer writes `completed` status
- **Tests:** `test_continuation_state_machine.py`, `test_continuations_service.py`, `test_continue_api.py`

### PR-FH20: Refresh-Safe Idempotency
- **Status:** Complete
- **Backend Changes:**
  - `ContinuationResponse` schema with `created` boolean
  - Duplicate idempotency key returns existing continuation with `created: false`
  - GET continuation status endpoint
- **Frontend Changes:**
  - `PersistedContinuationIntent` interface with `dispatched` flag
  - localStorage with 24h TTL (replaces sessionStorage)
  - Restore `isContinuing` and `outcomeUnknown` on page load
  - Clear intent on terminal status or non-perspectives_ready transition
  - `RunDetailClient.tsx` differentiates "request failed" from "outcome unknown"
  - `PerspectivesReadyAction` supports `outcomeUnknown` prop
- **Tests:** `useRunWorkspace.test.ts` (10 tests: POST timeout, page refresh, duplicate click, terminal cleanup, stale intent expiry)

### PR-FH21: PostgreSQL Schema Contract
- **Status:** Complete
- **Changes:**
  - `scripts/check-alembic-heads.sh` — standalone script for CI
  - `scripts/check-schema-drift.sh` — detects schema drift
  - `test_schema_contract.py` expanded with status value tests and uniqueness constraint tests
  - `test_migrations.py` expanded with continuation tables, billing tables, and head matching tests
  - `ci.yml` updated to use standalone scripts + drift check
- **CI Integration:** Single head verification and schema drift check in `backend-postgres-test` job

## Phase 2 — Enforcement and Visibility

### PR-FH22: Observability Wiring
- **Status:** Complete
- **Changes:**
  - `RequestIDMiddleware` enhanced with Prometheus metrics recording
  - Request duration tracking with path normalization (UUID/numeric ID replacement)
  - Slow request logging (>2s threshold)
  - X-Request-ID propagation on all responses
- **Metrics:** HTTP request counts, duration histograms, status codes

### PR-FH23: Feature Flag Enforcement
- **Status:** Complete (existing infrastructure)
- **Existing:**
  - `apps/web/lib/feature-flags.ts` with 13 flags
  - `apps/api/config.py` with startup validation
  - `apps/api/routes/features.py` public flags endpoint
  - `apps/api/orchestration/pipeline.py` staged pause gate

### PR-FH26: Authenticated Rate-Limit Identity
- **Status:** Complete
- **Changes:**
  - `_resolve_identity()` — priority: user ID > API key fingerprint > IP
  - Key format: `wl:user:<id>`, `wl:api_key:<hash>`, `wl:ip:<ip>`
  - SSE-specific budget (10 connections per 60s window)
  - Rate limit headers on all responses: `X-RateLimit-Budget`, `X-RateLimit-Cost`, `X-RateLimit-Action`, `X-RateLimit-Window`
  - Metrics integration for rate limit rejections

## Phase 3 — Financial and UX Completion

### PR-FH24: Mobile Decision Report
- **Status:** Complete
- **New Components:**
  - `ReportSectionNav.tsx` — sticky section navigation (desktop tabs, mobile dropdown)
  - `ReportFocusMode.tsx` — full-screen focus mode with floating ToC
  - `VerificationStatus.tsx` — verification status badge (verified/warning/error/unknown)
- **Existing Components:** `DecisionReportView`, `ModelPositionsTable`, `RiskMatrix`, `SemanticAlignmentSection` already have mobile support

### PR-FH25: Billing Reconciliation
- **Status:** Complete
- **New Models:**
  - `BillingReconciliationRun` — audit trail for reconciliation executions
  - `BillingReconciliationDiscrepancy` — individual discrepancies found
- **Enhanced `reconciliation.py`:**
  - Comprehensive checks: negative tokens, negative debates, excessive usage, zero tokens with active debates
  - Database persistence of run records and discrepancies
  - Error handling with status tracking
  - `get_reconciliation_runs()` and `get_reconciliation_discrepancies()` for admin viewing
- **Admin Endpoints:**
  - `GET /billing/admin/reconciliation/runs` — list recent runs
  - `GET /billing/admin/reconciliation/runs/{run_id}/discrepancies` — view discrepancies
  - `POST /billing/admin/reconciliation/run` — manual trigger

## Phase 4 — Evidence and Diligence

### PR-FH27: Production Topology Smoke
- **Status:** Complete
- **New Files:**
  - `docker-compose.smoke.yml` — networked topology (web reaches API via `consultaion-smoke-api:8000`)
  - `.github/workflows/docker-smoke.yml` — CI workflow with health checks, API verification, Alembic head check
  - `scripts/smoke-docker.sh` — standalone smoke test script
- **Features:**
  - Health check polling with timeout
  - Container log collection on failure
  - Automatic cleanup on exit
  - Alembic single-head verification inside container

### PR-FH28: Documentation Truthfulness
- **Status:** Complete
- **Created:**
  - `docs/engineering/implementation-status.md` — this file
  - `docs/engineering/test-evidence.md` — test results and coverage
- **Reconciled:** README.md and WALKTHROUGH.md overclaiming language.

---

## Phase 5 — Production Hardening Completion (PR-FH39 through PR-FH50)

### PR-FH39: Immutable Continuation Attempts
- **Status:** Complete
- **Changes:**
  - Terminal states (completed/failed/cancelled/paused) have empty transition sets in `ALLOWED_CONTINUATION_TRANSITIONS`, making retries impossible without a new continuation record.
  - UNIQUE(debate_id, idempotency_key) constraint on `DebateContinuation` prevents duplicate idempotency keys.
  - FK `retry_of_continuation_id` → `debate_continuation.id` with `ondelete="SET NULL"` for referential integrity on parent deletion.
  - Migration `p123_cont_retry_fk` applies constraints.

### PR-FH40: Continuation Contract and Recovery Loop
- **Status:** Complete
- **Changes:**
  - `useRunWorkspace.ts` stores `response.continuation_id` (not `response.id`) for correct continuation tracking.
  - Mount-based recovery checks persisted intent from localStorage.
  - Duplicated-action protection disables buttons while tracking in-flight requests.
  - Resolve endpoint called for unknown continuation IDs to clean up stale state.

### PR-FH41: Real Schema Drift
- **Status:** Complete
- **Changes:**
  - `scripts/check-schema-drift.py` uses `compare_metadata()` for reliable drift detection.
  - `test_model_migration_parity.py` validates: revision lengths (≤32 chars), chain uniqueness, single head, and critical table presence.

### PR-FH42: Trusted Rate-Limit Identity
- **Status:** Complete
- **Changes:**
  - `rate_limit_identity.py` validates cookie JWT signature and API keys via DB cache.
  - Respects `TRUSTED_PROXY_CIDRS` for X-Forwarded-For resolution.
  - Bounded cache with configurable TTL for API key lookups.

### PR-FH43: SSE Concurrent Stream Limiter
- **Status:** Complete
- **Changes:**
  - `StreamLeaseManager` class in `sse_backend.py` using Redis sorted sets (or in-memory fallback).
  - Lease-based concurrent stream limit per debate_id (default: 5 concurrent streams).
  - Returns HTTP 503 with `Retry-After: 30` when limit is exceeded.
  - Leases auto-expire after configurable TTL (default: 5 minutes).
  - Configurable via `SSE_MAX_CONCURRENT_STREAMS` and `SSE_LEASE_TTL_SECONDS`.

### PR-FH44: Report Provenance & Mobile Report Canonicalization
- **Status:** Complete
- **Changes:**
  - `DecisionReportView.tsx` renders `FallbackResponseCard`, `UnstructuredSynthesisCard`, `ReportGenerationFailedCard` based on API response.
  - No `buildFallbackReport` function exists — all branches derive from real API response fields.
  - Responsive model positioning grids, risk matrices, and focus mode viewport tracking.

### PR-FH45: Feature Flags Wiring
- **Status:** Complete
- **Changes:**
  - `FeatureGate` imported and wired in `RunDetailClient.tsx`:
    - `unifiedWorkspace` flag gates the workspace UI (header, stage rail, mobile bar, perspectives grid)
    - `mobileWorkspaceV2` flag gates `MobileStageBar`
    - `stagedDecisionPipelinePublic` flag gates `PerspectivesReadyAction`
  - `GET /api/v1/config/features` endpoint enriched with all operational trust flags.

### PR-FH46: ReconciliationWindow + Cost Reconciliation Refactor
- **Status:** Complete
- **Changes:**
  - `ReconciliationWindow` dataclass with `previous_utc_day()`, `month_to_date()`, `closed_month()` factory methods.
  - `reconcile_usage()` accepts `window` parameter; `_check_orphan_usage()` uses `window.start_at` / `window.end_at`.
  - `_get_model_pricing()` returns versioned pricing snapshots with effective date tracking for point-in-time cost recomputation.
  - Cost check compares recorded `SUM(cost_usd)` vs independently recomputed total using model × token counts.
  - Removed legacy `_period_start()` / `_period_end()` string-parsing helpers.

### PR-FH47: Celery Beat Schedules + Run Key + Redis Locking
- **Status:** Complete
- **Changes:**
  - `celery_app.py` uses `from celery.schedules import crontab` with proper `crontab()` objects.
  - `billing_tasks.py` generates deterministic `run_key` per window (`{window.label}:{run_type}`).
  - Redis distributed lock (`_acquire_reconciliation_lock` / `_release_reconciliation_lock`) prevents duplicate concurrent executions.
  - Lock TTL: 10 minutes; lock key format: `lock:billing-reconciliation:{run_key}`.

### PR-FH48: Fix Docker Compose Paths, Env, psycopg + Smoke Script
- **Status:** Complete
- **Changes:**
  - Compose uses `context: ./apps/api` (root-relative paths).
  - Environment: `ENV=test`, `APP_ENV=smoke`, `USE_MOCK=true`.
  - `psycopg` instead of `asyncpg` for synchronous driver compatibility.
  - Startup ordering: postgres → migrate → api → web.
  - Smoke script assertions fixed (eliminated subshell `read`), adds health checks and table verification.

### PR-FH49: Continuation Transition Metrics + Observability Wiring
- **Status:** Complete
- **Changes:**
  - `CONTINUATION_TRANSITIONS_TOTAL` counter (labels: `from_status`, `to_status`) — incremented on successful transitions.
  - `CONTINUATION_TRANSITION_CONFLICTS_TOTAL` counter (labels: `current_state`, `target_state`) — incremented on rejected transitions.
  - `PIPELINE_STAGE_DURATION_SECONDS` histogram (labels: `stage`, `mode`) — records stage execution time in `pipeline.py`.
  - `PIPELINE_STAGE_FAILURES_TOTAL` counter (labels: `stage`, `mode`) — incremented on stage failures.
  - `SYNTHESIS_RESULTS_TOTAL` and `VERIFICATION_RESULTS_TOTAL` counters.
  - `SSE_RECONNECTS_TOTAL` counter.
  - Console span exporter conditional on `APP_ENV in ("development", "test", "smoke")` to prevent production log spam.

### PR-FH50: Documentation Updates
- **Status:** Complete
- **Changes:**
  - SSE ops guide: added `SSE_MAX_CONCURRENT_STREAMS` and `SSE_LEASE_TTL_SECONDS` env vars.
  - Feature flags reference: enriched with all operational trust flags.
  - Implementation status: updated through FH50.
  - Changelog: entries for all PRs.
