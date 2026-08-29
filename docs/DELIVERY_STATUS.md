# Delivery status

**As of:** 2026-08-29 UTC
**Branch evidence:** the supplied `work` branch contains `a385c96` followed by the M0/M1 repair in this change. The checkout has no configured Git remote, so its association with GitHub PR #64 cannot be queried locally; this change continues the existing branch and does not create or merge a PR.

## Incident finding

The OpenRouter “no request” symptom was a deterministic routing/credential regression. Key-isolation hardening removed ambient key export, while gateway calls still supplied only BYOK/request keys. In an OpenRouter-only deployment, Arena registry filtering hid direct-provider seats; remaining streaming calls resolved a canonical direct provider, passed no server key, and had no streaming fallback. Structured Debate could select a direct adapter and similarly omit both the matching server key and the OpenRouter fallback key. Failure therefore occurred before a valid OpenRouter HTTP request.

History places the originating explicit-key behavior in PS155 (`ba0d8b8`/`e75dff4`), before merge `4d6524c0`. The merge preserved that gateway behavior while adding execution fencing and error sanitization. Commit `e35186f` added server-key resolution, OpenRouter-reachable Arena seats, and fallback. This pass closed a remaining correctness hole in that fix: an adapter could emit a delta and then return an empty failed result, causing the gateway to start OpenRouter and splice two providers. The gateway now tracks the first delivered delta and returns the interrupted primary result without fallback.

## Verified provider branches

Mock-based tests now prove all of the following without provider network traffic:
- direct server credentials are preferred and OpenRouter is not called after direct success;
- a missing direct credential routes Arena streaming to OpenRouter;
- an empty pre-delta direct stream failure routes to OpenRouter;
- any first primary delta permanently disables streaming fallback;
- an OpenRouter-only configuration exposes the complete Arena seat manifest;
- Structured Debate fallback receives the server OpenRouter key;
- both primary and fallback calls retain the resolved canonical model identity.

## M0 evidence

The supported runtimes are installed but were not active initially: pyenv contains Python `3.11.15`, NVM contains Node `v20.20.2`, while shell defaults were Python 3.14 and Node 24. `scripts/setup.sh` now discovers and selects the preinstalled supported versions without installing runtimes, prints their actual versions, and remains caller-directory independent.

- `bash -n scripts/setup.sh`: passed.
- Clean-shell `env -i ... bash --noprofile --norc scripts/setup.sh`: selected the preinstalled Python 3.11.15 and Node 20.20.2, created `apps/api/.venv`, then stopped at dependency installation because DNS/package access failed. Pip reported `Failed to establish a new connection: [Errno -3] Temporary failure in name resolution` and ultimately `No matching distribution found for fastapi==0.141.1` because no index response was available.
- With Node 20.20.2 explicitly first on `PATH`, `npm run lint:urls` reached `npx tsx` but the registry returned `E403 403 Forbidden - GET https://registry.npmjs.org/tsx`. Root URL/color/i18n guards therefore could not start. This is package access, not a source failure.
- Frontend dependencies were already present. Under Node 20.20.2, ESLint, `tsc --noEmit`, 58 Vitest files / 392 tests, and the Next.js production build passed.

M0 is complete for all unblocked deterministic work. The sole M0 external blocker is dependency-index access needed to populate the clean Python 3.11 environment and root `node_modules`.

## M1 and affected backend evidence

The exact documented focused selection was executed with the available populated environment:

`pytest -q --no-cov tests/test_model_gateway.py tests/test_model_target_resolver.py tests/test_gateway_integration.py tests/test_debate_pipeline_integration.py tests/test_core_engine_recovery.py`

Result: **37 passed, 0 failed**. That populated environment is Python 3.14, not the acceptance runtime. The same command cannot yet run in the newly created Python 3.11 virtual environment because dependency-index access failed; no Python 3.11 result is claimed.

The previously observed failures were deterministic and were repaired:
- Async tests now force `DATABASE_URL_ASYNC` to the same session database as `DATABASE_URL`, rather than inheriting an unrelated externally supplied async URL. The affected integration tests no longer connect to an empty SQLite database.
- Database readiness now resolves the resettable engine from the `database` module at call time instead of retaining the pre-fixture engine imported during module initialization.
- SSE readiness now reports the underlying channel transport and separately reports `TerminalCommitGuard` as a wrapper.
- The hosted-credit failure test now creates the durable reservation required by the current exactly-once accounting contract instead of mutating the usage counter without a ledger identity.

Affected selection result: **15 passed, 0 failed** for `tests/test_model_gateway.py`, the refund test, the standard pipeline integration test, and SSE readiness test. Ruff passed for every changed Python file. The relevant mypy slice for `model_gateway/__init__.py` and `checks.py` passed.

## Milestone state

| Milestone | State | Evidence / blocker |
|---|---|---|
| M0 setup/evidence | **Complete except one external blocker** | Runtime auto-selection works; Python/root dependency installation is blocked by DNS/registry access. Existing frontend dependencies validate under Node 20. |
| M1 provider routing | **Deterministically green; Python 3.11 parity blocked** | 37/37 focused tests pass with mocks; clean 3.11 execution awaits dependency access. |
| M2 backend/database | **In progress** | Complete backend suite meets coverage but retains 14 deterministic failures; Ruff, CI mypy, one Alembic head, SQLite upgrade, and SQLite schema drift pass. PostgreSQL is unavailable. |
| M3 frontend/contracts | **Partially verified** | Frontend lint/typecheck/392 tests/build pass under Node 20; root guards are registry-blocked and OpenAPI drift was not run. |
| M4 packaged runtime | **Not claimed** | Docker and Redis SSE were not verified. |
| M5 production | **Not claimed** | No real OpenRouter, Render, Vercel, GitHub Actions, or production deployment verification was performed. |

## Exact external blocker and next executable action

The remaining package blocker is outbound dependency-index access: pip receives DNS resolution failures and npm receives HTTP 403 for `https://registry.npmjs.org/tsx`. Once access is restored, rerun `scripts/setup.sh`, then rerun M1 and the complete M2 suite from `apps/api/.venv` under Python 3.11. No credential, billing, deployment, or production action was attempted.

## GitHub pull-request review

On 2026-08-29, the requested review of the most recently opened pull request
could not be performed from this checkout. The repository has no configured Git
remote, `gh auth status` reports that no GitHub host is authenticated, and an
unauthenticated request to
`https://api.github.com/repos/kriptokasim/Consultaion/pulls?state=open` was
rejected by the environment's CONNECT proxy with HTTP 403. No pull request was
inspected or merged, and no mergeability or usefulness claim is made without
the remote diff and checks. The next executable action is to provide GitHub
network access plus an authenticated token with read access and, only if the
reviewed change is useful and green, merge permission.

## M2 backend/database evidence — 2026-08-29

The complete backend command was run with the populated Python 3.14.4 virtual
environment because the preinstalled Python 3.11.15 runtime has no dependencies
and package-index access remains blocked. The first run produced **1056 passed,
78 failed, 6 errors, 17 skipped** with 76.23% coverage. Investigation identified
test-contract drift and two suite-wide isolation leaks rather than a coverage
failure. After repairing typed staged-pipeline configuration, coding-worker and
router patch targets, correlation `ContextVar` token restoration, and FastAPI
dependency-override cleanup, the widest rerun produced **1126 passed, 14 failed,
17 skipped** with 78.39% coverage. M2 is not marked green while those 14
deterministic failures remain.

Commands and outcomes:

- `pytest -q`: 1126 passed, 14 failed, 17 skipped; coverage 78.39% (threshold
  satisfied). Runtime: Python 3.14.4, which is evidence only—not Python 3.11
  acceptance.
- `ruff check apps/api`: passed.
- the exact CI mypy slice for usage ledger, billing service, Stripe provider,
  and LLM action guard: passed.
- `bash ../../scripts/check-alembic-heads.sh` from `apps/api` with the populated
  virtualenv on `PATH`: one head, passed.
- `DATABASE_URL=sqlite:////tmp/consultaion_m2.db alembic upgrade head`: passed.
- schema drift against that migrated SQLite database: passed with no
  data-bearing table/column drift.
- M1 focused provider suite: 37 passed, 0 failed.
- The final affected selection covering staged/coding/router contracts,
  correlation restoration, in-memory SSE, admin metrics, API-key audit
  atomicity, public event access, and export override isolation: **95 passed,
  0 failed**.

PostgreSQL 16 and Docker are not installed (`docker`, `psql`, `postgres`, and
`pg_ctl` are absent), so the PostgreSQL workflow slice could not run. No
PostgreSQL, Docker, Redis, or production verification is claimed. Remaining M2
work is deterministic test repair plus Python 3.11 parity after dependency
access is restored; the infrastructure blocker for the database-specific slice
is the absence of both a PostgreSQL 16 service/client and Docker.
