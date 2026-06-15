# Final Hardening Patchset — Implementation Plan (PR-FH29 → FH38)

## Phase 1: State Correctness

### PR-FH29 — Continuation Lifecycle State Machine

**Files to modify:**
- `apps/api/models.py` — Add `paused_at` field, `retry_of_continuation_id` field to `DebateContinuation`
- `apps/api/services/continuations.py` — Add `ALLOWED_CONTINUATION_TRANSITIONS` map, validate transitions against map, add `paused` to `_apply_continuation_updates`
- `apps/api/routes/debates.py` — Replace direct ORM status mutations in `continue_debate_run` with calls to `transition_continuation_sync`. On retry of failed continuation, create NEW record with `retry_of_continuation_id` instead of resetting in-place
- `apps/api/orchestrator.py` — Add `running → paused` transition when `result.status == "perspectives_ready"` during resume
- New migration: `apps/api/alembic/versions/p121_add_paused_status_and_retry_of.py` — Add `paused_at` column, `retry_of_continuation_id` column, index on `(debate_id, status)`
- `apps/api/tests/test_continuation_state_machine.py` — Expand to 16 tests covering all transitions, immutability of terminals, pause behavior, concurrency

**Key changes:**
1. Central transition map in `continuations.py`:
```python
ALLOWED_CONTINUATION_TRANSITIONS = {
    "requested": {"preflight_passed", "failed", "cancelled"},
    "preflight_passed": {"dispatched", "failed", "cancelled"},
    "dispatched": {"running", "failed", "cancelled"},
    "running": {"paused", "completed", "failed"},
    "paused": set(),
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}
```
2. `_apply_continuation_updates` adds `paused_at` timestamp for `paused` status
3. Route handler replaces all `continuation_record.status = "..."` with `transition_continuation_sync(session, continuation_record.id, expected, target)`
4. Failed retry: create new `DebateContinuation` with `retry_of_continuation_id=old_id`, new idempotency key required
5. Orchestrator: when resume returns `perspectives_ready`, transition continuation to `paused`

### PR-FH30 — Durable Idempotency and Browser Recovery

**Files to modify:**
- `apps/web/hooks/useRunWorkspace.ts` — Expand `PersistedContinuationIntent` with `continuationId`, `phase`, `expiresAt`, `updatedAt`. Storage key → `consultaion:continuation:<debateId>`. Don't clear intent after POST success. Only clear on terminal or confirmed paused
- `apps/web/hooks/useRunWorkspace.test.ts` — Expand tests to cover new phases, continuationId persistence, refresh during running, paused confirmation
- `apps/api/routes/debates.py` — Add `POST /debates/{debate_id}/continuations/resolve` endpoint for idempotency-key-based lookup
- `apps/api/schemas.py` — Add `ContinuationResolveRequest` schema
- `apps/web/components/workspace/PerspectivesReadyAction.tsx` — Update to handle paused state
- `apps/web/app/(app)/runs/[id]/RunDetailClient.tsx` — Wire `retryRun` (currently destructured but unused)

**New persisted interface:**
```typescript
interface PersistedContinuationIntent {
  debateId: string
  continuationId?: string
  idempotencyKey: string
  target?: string
  createdAt: string
  updatedAt: string
  phase: "intent_created" | "request_sent" | "server_acknowledged" | "tracking"
  expiresAt: string
}
```

### PR-FH31 — PostgreSQL Migration and Schema Contract Repair

**Files to modify:**
- `.github/workflows/ci.yml` — Fix `backend-postgres-test` job: scripts run from `apps/api` but scripts are at repo root. Use `bash ../../scripts/check-alembic-heads.sh` or change working-directory
- `scripts/check-schema-drift.sh` — Rename to `check-database-at-head.sh`. Create new `check-schema-drift.sh` that uses Alembic `compare_metadata()` API for real drift detection
- New migration: `p121_*` for billing reconciliation tables + continuation paused_at
- `apps/api/tests/test_schema_contract.py` — Expand to assert column names, types, nullability, defaults, FKs, unique constraints, indexes for critical tables
- `apps/api/tests/test_alembic_revision_ids.py` — New test: assert all revision IDs ≤ 32 chars, unique, valid chain
- `apps/api/tests/test_model_migration_parity.py` — New test: compare SQLModel metadata against Alembic migration head

## Phase 2: Protection and Financial Integrity

### PR-FH32 — Authenticated Weighted Rate Limiting and SSE Protection ✅ DONE

**Files to modify:**
- `apps/api/middleware/weighted_rate_limit.py` — Major refactor:
  - Move GET/HEAD out of blanket exemption; classify reads into operation classes
  - SSE check before general GET handling
  - Add `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers
  - Identity: validate cookie JWT signature (not just check `request.state.user_id`), validate API key through service/cache
- New file: `apps/api/middleware/rate_limit_identity.py` — Extract identity resolution to dedicated module with cookie JWT validation, API key validation, trusted proxy handling
- New test files:
  - `apps/api/tests/test_weighted_rate_limit_identity.py`
  - `apps/api/tests/test_weighted_rate_limit_reads.py`
  - `apps/api/tests/test_sse_connection_limits.py`
  - `apps/api/tests/test_trusted_proxy_resolution.py`

### PR-FH33 — Real Internal Billing Reconciliation ✅ DONE

**Files to modify:**
- `apps/api/billing/reconciliation.py` — Complete rewrite:
  - Add `RECONCILIATION_VERSION = "v1"`
  - Token reconciliation: `BillingUsage.tokens_used` vs `SUM(LLMUsageLog.total_tokens)` per user per period
  - Per-model reconciliation: `BillingUsage.model_tokens` vs `SUM(LLMUsageLog.total_tokens GROUP BY model)`
  - Debate reconciliation: `BillingUsage.debates_created` vs count of completed debates
  - Hosted-credit reconciliation: credits reserved vs consumed vs refunded
  - Usage orphan checks: LLM usage without debate, completed debate without usage
  - Cost reconciliation: `SUM(LLMUsageLog.cost_usd)` vs internal
  - Tolerance configuration: `RECONCILIATION_TOKEN_TOLERANCE_ABSOLUTE`, `RECONCILIATION_COST_TOLERANCE_USD`, `RECONCILIATION_COST_TOLERANCE_PERCENT`
  - Idempotent runs with unique run key + distributed lock
- `apps/api/billing/models.py` — Expand `BillingReconciliationDiscrepancy` with `debate_id`, `provider`, `model`, `difference`, `difference_percent`, `status`, `resolution_note`, `resolved_by`, `resolved_at`, `source_reference`
- `apps/api/billing/routes.py` — Make admin trigger async (return `job_id` + `status: queued`)
- New migration: Add new columns to discrepancy table, add indexes
- Test files:
  - `apps/api/tests/test_billing_reconciliation.py` — 12+ tests
  - `apps/api/tests/test_billing_reconciliation_api.py`
  - `apps/api/tests/test_billing_reconciliation_idempotency.py`

### PR-FH34 — Scheduled Reconciliation and Operational Alerting ✅ DONE

**Files to create/modify:**
- New file: `apps/api/worker/billing_tasks.py` — Celery tasks: `billing.reconcile_previous_day`, `billing.reconcile_current_period`, `billing.reconcile_closed_period`
- `apps/api/worker/celery_app.py` — Register beat schedule
- `apps/api/observability/metrics.py` — Add reconciliation metrics: `reconciliation_runs_total`, `reconciliation_failures_total`, `reconciliation_discrepancies_total`, `reconciliation_duration_seconds`, `reconciliation_last_success_timestamp`
- `apps/api/billing/reconciliation.py` — Add distributed lock, alert emission

## Phase 3: Product Integration

### PR-FH35 — Mobile Report Integration and Fallback Integrity ✅ DONE

**Files to modify:**
- `apps/web/components/report/DecisionReportShell.tsx` — Replace inline focus mode with `ReportFocusMode` component, replace inline verification with `VerificationStatus`
- `apps/web/components/report/DecisionReportView.tsx` — Wire `ReportSectionNav`, use `synthesisStatus`/`fallbackResponse`/etc. props (currently dead), separate fallback rendering from structured report
- New file: `apps/web/components/report/FallbackResponseCard.tsx` — Distinct card for fallback responses (no fabricated confidence)
- Test files:
  - `apps/web/components/report/ReportSectionNav.test.tsx`
  - `apps/web/components/report/ReportFocusMode.test.tsx`
  - `apps/web/components/report/FallbackResponseCard.test.tsx`

### PR-FH36 — Feature Flag Enforcement ✅ DONE

**Files to modify:**
- `apps/web/lib/feature-flags.ts` — Add backend flags
- `apps/web/components/FeatureGate.tsx` — New gating component
- Frontend components: Gate `WorkspaceHeader`, `DesktopStageRail`, `MobileStageBar`, `PerspectivesGrid`, `PerspectivesReadyAction` behind `NEXT_PUBLIC_UNIFIED_WORKSPACE`
- Gate mobile report components behind `NEXT_PUBLIC_MOBILE_REPORT_V2`
- Backend: Gate staged pipeline behavior behind `STAGED_DECISION_PIPELINE`
- New test files:
  - `apps/web/components/FeatureGate.test.tsx`
  - `apps/web/tests/feature-flags.test.tsx`
  - `apps/api/tests/test_feature_flags.py`
  - `apps/api/tests/test_feature_flag_compatibility.py`

## Phase 4: Production Evidence

### PR-FH37 — Production Docker Topology and CI Repair ✅ DONE

**Files to modify:**
- `docker-compose.smoke.yml` — Complete rewrite: add postgres, redis, migrate service, correct build contexts, proper health checks (python -c for API, wget for web)
- `scripts/smoke-docker.sh` — Expand: run migrations, verify web-to-API proxy, create mock debate, verify tables exist
- `.github/workflows/docker-smoke.yml` — Update to match new compose, add artifact collection

### PR-FH38 — Observability Completion, Evidence, and Documentation ✅ DONE

**Files to modify:**
- `apps/api/observability/metrics.py` — Wire unreferenced gauges (SSE_STREAMS_ACTIVE, DB_POOL_*, REDIS_POOL_SIZE), add reconciliation metrics
- `apps/api/observability/tracing.py` — Add OTLP exporter option, add ASGI tracing middleware
- `docs/engineering/test-evidence.md` — Update with actual CI job list, commit SHA, coverage
- `docs/engineering/implementation-status.md` — Update all PR statuses
- `README.md`, `WALKTHROUGH.md` — Reconcile overclaiming language

## Implementation Order

1. PR-FH29 (continuation state machine) — foundation for everything
2. PR-FH31 (migration + schema contract) — must exist before FH30 can fully work
3. PR-FH30 (idempotency + browser recovery) — depends on FH29's paused status
4. PR-FH32 (rate limiting) — independent, can parallel with 1-3
5. PR-FH33 (reconciliation) — independent
6. PR-FH34 (scheduler) — depends on FH33
7. PR-FH35 (mobile report) — independent
8. PR-FH36 (feature flags) — depends on knowing all flag values
9. PR-FH37 (Docker) — independent
10. PR-FH38 (observability + docs) — last, after all code is final

## Estimated Files Changed/Created

~50-60 files total across all PRs.
