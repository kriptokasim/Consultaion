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
- **Status:** In Progress
- **Created:**
  - `docs/engineering/implementation-status.md` — this file
  - `docs/engineering/test-evidence.md` — test results and coverage
- **Remaining:** Reconcile README.md and WALKTHROUGH.md overclaiming language

## Verification

All frontend tests pass (121 tests across 19 files). TypeScript compilation clean. No regressions detected.

## Next Steps

1. Reconcile README.md and WALKTHROUGH.md with defensible language
2. Run full backend test suite against PostgreSQL
3. Deploy to staging for integration verification
