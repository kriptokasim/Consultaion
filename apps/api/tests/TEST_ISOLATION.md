# Test Isolation Strategy (Patchset 31.0)

This suite uses **Option B: truncate-all-tables between tests** to guarantee deterministic runs in any order.

## How it works
- `tests/conftest.py` sets `FASTAPI_TEST_MODE=1` and points `DATABASE_URL` to a unique SQLite DB for the session.
- The `reset_global_state` autouse fixture calls `truncate_all_tables()` before every test, then re-seeds billing plans via `seed_billing_plans()`.
- Provider health and SSE backends are reset per-test so background state cannot leak.

## Why truncate-all?
- Application code opens its own SQLModel sessions, so transaction-scoped fixtures could miss writes.
- Truncation with identity reset keeps sequence values predictable and avoids migration overhead.

## Local test commands
- Backend: `cd apps/api && pytest -q`
- Frontend E2E (requires running app): `cd apps/web && npm run test:e2e`

Keep new fixtures aligned with this pattern—add seed helpers for any new system tables you introduce.
