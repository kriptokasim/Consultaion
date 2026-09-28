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

## Auth signup FK-ordering hotfix — 2026-09-27

PR opened: [kriptokasim/Consultaion#86](https://github.com/kriptokasim/Consultaion/pull/86),
`fix(auth): stage signup audit rows after the user insert`, head
`claude/awesome-cori-3uho61` onto `main` at `9b41d0f`. Fixes a production
regression where every new email signup returned 400 `auth.email_exists` and
every first-time Google OAuth signup returned 500, because `AuditLog` inserts
were not ordered after their referenced `User` insert within the same flush
(no declared `relationship()` links the two models, so the ORM does not order
the inserts by that FK). `apps/api/audit.py` gained `stage_audit()`;
`apps/api/routes/auth.py`'s `register_user` and both Google callback handlers
now flush the user row before staging its audit row.

Commands and outcomes, all run under Python 3.11.15 in a fresh
`apps/api/.venv`. (Corrected 2026-09-27: an earlier version of this entry
reported a full-suite pass count from a run that shared its fixed-path SQLite
test database with a concurrent run; the figures below come from isolated
runs.)

- `cd apps/api && pytest -q --no-cov tests/test_auth_flows.py tests/test_google_auth.py tests/test_audit_transactions.py tests/test_audit_ip.py tests/test_audit_deletion.py tests/test_auth_cookies.py tests/test_auth_audit_fk_ordering.py`
  (the patchset's targeted selection, which includes the 3 new tests in
  `test_auth_audit_fk_ordering.py`): **26 passed**.
- `ruff check apps/api/audit.py apps/api/routes/auth.py apps/api/tests/test_auth_audit_fk_ordering.py`:
  passed.
- `cd apps/api && TMPDIR=<per-run dir> pytest -q --junitxml=...` (complete
  suite, not a partial selection), run separately on `main` (`9b41d0f`) and on
  this branch, each with its own `TMPDIR` because the suite's SQLite database
  path is fixed under the temp directory:
  - `main`: **26 failed, 1273 passed, 17 skipped**, coverage 78.96%.
  - this branch: **26 failed, 1276 passed, 17 skipped**, coverage 79.02%.
  - Per-test JUnit comparison: the failing sets are identical, and the only
    difference is the 3 new tests, which pass. All 26 failures are
    pre-existing on `main`; none are in auth/signup/audit code.

Why CI missed the bug: SQLite enforces foreign keys only on connections that
enable `PRAGMA foreign_keys`, and the shared test engine did not, so the
out-of-order `audit_log` insert succeeded in tests. PostgreSQL always enforces
the constraint, which is where it failed.

Not done in this PR, tracked as explicit follow-up: making the shared SQLite
test engine enforce FKs globally (not just in this new test's own fixture)
and fixing whatever latent bugs that reveals suite-wide; making 4xx
`AppError`s distinguishable in Sentry logs. Not code, and not attempted here:
confirming the production DB is at Alembic head, confirming Render's
pre-deploy step runs `alembic upgrade head`, and — only after this PR merges
and deploys — one real production email signup and one real first-time
Google signup to confirm both return 2xx.

## FK enforcement (Patch 2) and CI gate repair — 2026-09-27

Branch `claude/nice-ramanujan-3p0qlk`, stacked on PR #86. Both SQLAlchemy
engines now run `PRAGMA foreign_keys=ON` on every SQLite connection, and
`tests/utils.truncate_all_tables` restores the pragma outside its transaction
(SQLite ignored it inside one, returning pooled connections with enforcement
off). Enforcement revealed 97 additional failing tests; all were fixed at the
source without skips or disabling enforcement. It also exposed a latent bug in
`record_audit` (same insert-order shape as the signup bug), now fixed.

Main's CI was red before any tests ran: `ruff` (71 errors) blocked pytest;
the PostgreSQL migration/drift steps failed because config requires `ENV`
and a non-placeholder `JWT_SECRET` with a non-SQLite URL; the SQLite branch of
migration p170 had 9 columns for 8 values; `docs/openapi.json` had drifted;
ESLint linted a vendored three.js bundle; `npm audit --audit-level=high`
failed on a critical Next.js advisory. All are fixed on this branch.

Commands and outcomes (Python 3.11.15, Node 20.20.2):

- `ruff check apps/api`: passed (0 errors; `main`: 71).
- CI mypy slice: passed.
- `cd apps/api && pytest -q` with the CI `backend-test` environment
  (`DATABASE_URL=sqlite:///./ci_test.db`, isolated `TMPDIR`): **1309 passed,
  0 failed, 17 skipped**, coverage 79.23% (`main`: 26 failed).
- Same suite against a local PostgreSQL 16 (native FK enforcement, as in
  production): **1309 passed, 0 failed, 17 skipped**.
- On PostgreSQL 16: `check-alembic-heads.sh` one head; `alembic upgrade head`
  passed; `check-schema-drift.sh` "No drift"; the CI PostgreSQL slice
  **38 passed**.
- `python scripts/migrate_database.py` and `--check` on SQLite: passed;
  `python scripts/audit_alembic_revisions.py --ci`: passed (warnings only).
- `./scripts/check_openapi_drift.sh`: passes once the regenerated spec is
  committed; the export is deterministic.
- `apps/web`: `eslint .` 0 problems; `tsc --noEmit` passed; Vitest 400 passed;
  `npm run build` passed on Next 15.5.26; `npm audit --audit-level=high`
  passed (2 moderate, dev-only vitest findings remain; fix needs vitest 4).

Blockers and decisions recorded separately, not code:

- Production must set `GROQ_API_KEY` for the free Arena to serve all four
  seats: `9b41d0f` made the first free seat Groq-direct and deliberately never
  routed through OpenRouter. Without the key the seat is omitted, not
  misrouted.
- Render's pre-deploy `alembic upgrade head` must run with `ENV` set; config
  refuses to start without it against PostgreSQL.
- GitHub Actions results for this branch are not yet observed.

## Run engine audit fixes — 2026-09-28

Same branch. Traced one run from the Run button through `POST /debates`,
dispatch, the orchestrator, the Arena fan-out, synthesis and the decision
report to the terminal event, and fixed the defects found. Each fix has a
regression test that fails without it.

- SSE `/stream` held its request DB session for the whole stream. Reproduced
  on PostgreSQL 16 with a one-connection pool: one open stream made an
  unrelated `GET /debates/{id}` return 500 after the pool timeout. The route
  now closes the session before streaming.
- Celery: every other run in a worker process failed with `RuntimeError: Event
  loop is closed` (reproduced), because the async Redis pool, SSE backend and
  async DB pool stayed bound to the first task's loop. Tasks now release them
  before their loop closes. `debates.run` has a soft time limit (default
  1800s) and is not retried after hitting it. Production currently dispatches
  inline, so this was latent there.
- Orchestrator: an error after the terminal commit (publish, email,
  bookkeeping) ran the failure handler, which sent a false failure alert and
  skipped credit settlement and the terminal event. Post-commit steps are
  isolated. Failed compare/conversation runs emitted `final`; they now emit
  `debate_failed`.
- `POST /debates`: honours `X-Idempotency-Key` (stored in
  `usage_ledger_entry`, no migration). After a DB error the refund ran in a
  failed transaction and leaked the hourly run slot; it now rolls back first.
  Rate limiting resolves the client IP through the trusted-proxy helper. The
  response no longer lists which provider keys the deployment holds.
- Web: the Run button ignores clicks while creation is in flight and sends one
  idempotency key per start intent.
- Arena: synthesis used the router's default model (a free model on an
  OpenRouter-only deployment). It now uses `ARENA_SYNTHESIS_MODEL` if set,
  else the best panel model that answered. A partial quorum was reported as
  `all_models_failed` with `successful_count=0`. A stream that failed after
  output started paid for a second full call.
- Report: draft/repair/revise ignored `SYNTHESIS_MAX_TOKENS` (fixed 1500), and
  repair ran on the default model. Missing critic scores were recorded as 1.0.

Commands and outcomes (Python 3.11.15, Node 20.20.2):

- `cd apps/api && pytest -q` with the CI `backend-test` environment, isolated
  `TMPDIR`: **1333 passed, 0 failed, 17 skipped**, coverage 79.68%.
- `ruff check apps/api`: passed. CI mypy slice: passed.
- `./scripts/check_openapi_drift.sh`: up to date.
- `apps/web`: `eslint .` 0 problems; `tsc --noEmit` passed; Vitest **402
  passed**; `npm run build` passed.
- Not re-run for this change: the full suite on PostgreSQL. Only the SSE
  connection-pinning reproduction ran against PostgreSQL 16.

Not changed, by decision:

- Setting `ARENA_SYNTHESIS_MODEL` to a paid model (e.g. the proxy `chair`
  deployment) is a cost decision for the operator. `chair` also needs a
  `MODEL_MAP` entry before the gateway can resolve it.
- The per-event Redis lock in the SSE backend costs several round trips per
  event. This is a performance item, not a correctness bug.
- `choose_queue_for_debate` keys on a config `mode` of `fast`/`deep` that runs
  never set, so every run uses the default queue. Workers consume that queue,
  so nothing is misrouted.
