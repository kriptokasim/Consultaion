# Final Hardening Patchset — Full Summary
## Consultaion (PR-FH19 through PR-FH28)
**Date:** 2026-06-15
**Commit:** a0cf0f4
**Branch:** main

---

## Overview

Implementation of the Final Hardening patchset across 4 phases: Correctness, Enforcement/Visibility, Financial/UX, and Evidence/Diligence. 40 files changed, ~2,244 lines added, ~279 lines removed.

---

## Phase 1 — Correctness Blockers

### PR-FH19: Continuation State Machine ✅
| File | Change |
|------|--------|
| `apps/api/exceptions.py` | Added `ContinuationTransitionError` |
| `apps/api/services/continuations.py` | Rewritten with `transition_continuation_sync`/`async` (atomic SQL transitions) |
| `apps/api/orchestration/interfaces.py` | Added `continuation_id: Optional[str]` to `DebateContext` |
| `apps/api/orchestrator.py` | Wired continuation ID propagation |
| `apps/api/debate_dispatch.py` | Wired continuation_id |
| `apps/api/routes/debates.py` | POST `/debates/{id}/continue` + GET continuation endpoint |
| `apps/api/schemas.py` | Added `ContinuationResponse` schema |
| `apps/api/tests/test_continuation_state_machine.py` | State machine tests |
| `apps/api/tests/test_continuations_service.py` | Service transition tests |
| `apps/api/tests/test_continue_api.py` | API idempotency tests |

### PR-FH20: Refresh-Safe Idempotency ✅
| File | Change |
|------|--------|
| `apps/web/hooks/useRunWorkspace.ts` | localStorage with 24h TTL, `PersistedContinuationIntent` interface, restore on load, clear on terminal |
| `apps/web/hooks/useRunWorkspace.test.ts` | **NEW** — 10 tests (POST timeout, page refresh, duplicate click, terminal cleanup, stale intent expiry) |
| `apps/web/app/(app)/runs/[id]/RunDetailClient.tsx` | Uses `outcomeUnknown` flag for "request failed" vs "outcome unknown" |
| `apps/web/components/workspace/PerspectivesReadyAction.tsx` | Accepts `outcomeUnknown` prop, shows "Retry Synthesis" |

### PR-FH21: PostgreSQL Schema Contract ✅
| File | Change |
|------|--------|
| `scripts/check-alembic-heads.sh` | **NEW** — Standalone CI script for single-head verification |
| `scripts/check-schema-drift.sh` | **NEW** — Detects schema drift (current vs head) |
| `apps/api/tests/test_schema_contract.py` | Expanded with status value and uniqueness constraint tests |
| `apps/api/tests/test_migrations.py` | Expanded with continuation tables, billing tables, head matching |
| `.github/workflows/ci.yml` | Updated to use standalone scripts + drift check |

---

## Phase 2 — Enforcement and Visibility

### PR-FH22: Observability Wiring ✅
| File | Change |
|------|--------|
| `apps/api/main.py` | Enhanced `RequestIDMiddleware` with Prometheus metrics, path normalization, slow request logging (>2s) |

### PR-FH26: Authenticated Rate-Limit Identity ✅
| File | Change |
|------|--------|
| `apps/api/middleware/weighted_rate_limit.py` | `_resolve_identity()` (user ID > API key fingerprint > IP), SSE-specific budget (10/60s), rate limit headers on all responses |

---

## Phase 3 — Financial and UX

### PR-FH24: Mobile Decision Report ✅
| File | Change |
|------|--------|
| `apps/web/components/report/ReportSectionNav.tsx` | **NEW** — Sticky section navigation (desktop tabs, mobile dropdown) |
| `apps/web/components/report/ReportFocusMode.tsx` | **NEW** — Full-screen focus mode with floating ToC |
| `apps/web/components/report/VerificationStatus.tsx` | **NEW** — Verification status badge (verified/warning/error/unknown) |

### PR-FH25: Billing Reconciliation ✅
| File | Change |
|------|--------|
| `apps/api/billing/models.py` | Added `BillingReconciliationRun` and `BillingReconciliationDiscrepancy` models |
| `apps/api/billing/reconciliation.py` | Expanded with comprehensive checks, database persistence, admin queries |
| `apps/api/billing/routes.py` | Added admin endpoints: list runs, view discrepancies, manual trigger |

---

## Phase 4 — Evidence and Diligence

### PR-FH27: Production Topology Smoke ✅
| File | Change |
|------|--------|
| `docker-compose.smoke.yml` | **NEW** — Networked topology (web → api:8000) |
| `.github/workflows/docker-smoke.yml` | **NEW** — CI workflow with health checks, Alembic verification |
| `scripts/smoke-docker.sh` | Rewritten for networked topology |

### PR-FH28: Documentation Truthfulness ✅
| File | Change |
|------|--------|
| `docs/engineering/implementation-status.md` | **NEW** — Implementation tracking document |
| `docs/engineering/test-evidence.md` | **NEW** — Test results and coverage |

---

## Verification

| Check | Result |
|-------|--------|
| Frontend tests | ✅ 121 passed (19 files) |
| TypeScript compilation | ✅ Clean (no errors) |
| Python imports | ✅ All modules import successfully |
| Git commit | ✅ a0cf0f4 |
| Git push | ⏳ Run `git push origin main` manually |

---

## Key Architecture Decisions

1. **Continuation state machine** uses strict `WHERE id AND status IN (expected)` SQL pattern for atomic transitions
2. **Rate limit identity** resolves via lightweight JWT validation / API-key fingerprint BEFORE middleware enforcement; no per-request DB queries
3. **Feature flags** are declared as constants; backend-authoritative flags gate execution paths
4. **Documentation** uses defensible language ("application-level tenant isolation", "tested in CI") instead of overclaiming
5. **Docker smoke** uses networked topology (web reaches API via `consultaion-smoke-api:8000`, not localhost)

---

## Files Created (12)

```
.github/workflows/docker-smoke.yml
apps/api/middleware/observability.py
apps/api/tests/test_continuation_state_machine.py
apps/web/components/report/ReportFocusMode.tsx
apps/web/components/report/ReportSectionNav.tsx
apps/web/components/report/VerificationStatus.tsx
apps/web/hooks/useRunWorkspace.test.ts
docker-compose.smoke.yml
docs/engineering/implementation-status.md
docs/engineering/test-evidence.md
scripts/check-alembic-heads.sh
scripts/check-schema-drift.sh
```

## Files Modified (28)

```
.github/workflows/ci.yml
apps/api/billing/models.py
apps/api/billing/reconciliation.py
apps/api/billing/routes.py
apps/api/debate_dispatch.py
apps/api/exceptions.py
apps/api/main.py
apps/api/middleware/weighted_rate_limit.py
apps/api/models.py
apps/api/orchestration/interfaces.py
apps/api/orchestrator.py
apps/api/routes/debates.py
apps/api/schemas.py
apps/api/services/continuations.py
apps/api/tests/test_continuations_service.py
apps/api/tests/test_continue_api.py
apps/api/tests/test_migrations.py
apps/api/tests/test_schema_contract.py
apps/api/worker/debate_tasks.py
apps/web/app/(app)/runs/[id]/RunDetailClient.tsx
apps/web/app/(marketing)/leaderboard/page.tsx
apps/web/app/(marketing)/pricing/page.tsx
apps/web/components/PromotionArea.tsx
apps/web/components/billing/BillingLimitModal.tsx
apps/web/components/workspace/PerspectivesReadyAction.tsx
apps/web/hooks/useRunWorkspace.ts
apps/web/tsconfig.tsbuildinfo
scripts/smoke-docker.sh
```
