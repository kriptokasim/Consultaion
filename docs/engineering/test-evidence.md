# Test Evidence — Final Hardening Patchset

## Frontend Test Results

**Total:** 121 tests passed across 19 test files

### useRunWorkspace.test.ts (10 tests)
- persists intent with dispatched=false before POST
- restores isContinuing on page load when intent has dispatched=true
- restores isContinuing on page load when intent has dispatched=false
- does not restore expired intent (stale intent expiry)
- clears intent when debate becomes terminal
- reuses idempotency key when clicking while intent already persisted
- handles POST failure and leaves intent for retry
- handles POST timeout and leaves intent for retry
- shows outcomeUnknown=true when page refreshes after successful POST
- cleans up intent when debate transitions out of perspectives_ready (undelivered)

### RunDetailClient.test.tsx (3 tests)
- renders loading skeleton when workspace status is loading
- renders error alert when workspace status has error
- renders running workspace view when debate is active

### Other Test Files (108 tests across 17 files)
All existing tests continue to pass with no regressions.

## Backend Test Coverage

### Schema Contract Tests (test_schema_contract.py)
- `test_database_table_existence` — verifies 32 core tables
- `test_debate_continuation_schema_contract` — 17 columns verified
- `test_debate_stage_checkpoint_schema_contract` — 12 columns verified
- `test_debate_continuation_status_values` — status column type check
- `test_debate_stage_checkpoint_status_values` — status column type check
- `test_debate_continuation_has_unique_idempotency_key` — uniqueness constraint

### Migration Tests (test_migrations.py)
- `test_000_postgres_migration` — runs Alembic upgrade head
- `test_001_tables_exist_after_migration` — verifies core tables
- `test_002_continuation_tables_exist` — verifies debate_continuation and debate_stage_checkpoint
- `test_003_billing_tables_exist` — verifies billing_plan, billing_subscription, billing_usage
- `test_004_alembic_current_matches_head` — verifies no pending migrations

### Continuation State Machine Tests
- `test_continuation_state_machine.py` — strict SQL transition pattern
- `test_continuations_service.py` — sync/async transition APIs
- `test_continue_api.py` — API idempotency handling

## TypeScript Compilation

No TypeScript errors in frontend codebase. Clean compilation across all components.

## CI Pipeline

### Required Blocking Jobs
1. `backend-unit` — Python unit tests (SQLite)
2. `backend-postgres-test` — PostgreSQL integration tests + schema drift check
3. `frontend-build` — Next.js production build
4. `e2e-test` — Playwright E2E tests
5. `docker-smoke` — Docker container health checks
6. `migration-contract` — Alembic single-head verification
7. `openapi-drift-check` — API contract drift detection
8. `i18n-parity` — Internationalization parity check
9. `security-scan` — gitleaks + bandit + pip-audit + npm audit

### New CI Steps
- `Verify Single Alembic Migration Head` — uses `scripts/check-alembic-heads.sh`
- `Check Schema Drift` — uses `scripts/check-schema-drift.sh`
- `docker-smoke` workflow — builds containers, verifies health, checks Alembic head

## Docker Smoke Test

- Networked topology: web reaches API via `consultaion-smoke-api:8000`
- Health check polling with 30 attempts, 2s interval
- Alembic single-head verification inside container
- Container log collection on failure
- Automatic cleanup on exit
