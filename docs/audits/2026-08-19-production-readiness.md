# Production Readiness Audit — 2026-08-19

## Scope

This audit reviews the Consultaion repository after `main` merge commit `f88907e0887d2e2b5f2278b9aab4c8abfe139175` and the post-merge CI hardening work that followed it. The goal is to separate actual production defects from test/configuration drift, remove misleading diligence claims, and make the enforced CI gates trustworthy enough to support deployment and technical diligence.

This document records engineering evidence. It is not a claim that a green CI pipeline proves the absence of every defect, security issue, or operational incident.

## Executive assessment

The baseline repository contained a broad and useful quality/security pipeline, but its signal had degraded in several places. A large backend failure count was dominated by deterministic test drift and async test-isolation problems rather than one systemic application failure. Several genuine production-readiness issues were also confirmed and fixed in this follow-up branch.

The most important outcome is that production code and test infrastructure are now being evaluated separately:

- real application behavior is fixed when the runtime contract is wrong;
- stale tests are updated when they contradict the canonical runtime contract;
- CI warnings or temporary diagnostics are not represented as application regressions;
- dependency-security exceptions are removed once a fixed release is available;
- diligence documentation describes the gates that are actually enforced.

## Confirmed production/runtime findings

### 1. Auth configuration failures were classified as provider outages

**Severity:** Medium

`get_web_app_origin()` used the provider circuit-breaker error class for a missing server-side frontend origin. That made a persistent operator configuration problem look like a retryable provider outage.

**Remediation:**

- added a dedicated `ConfigurationError` class with HTTP 500 / non-retryable semantics;
- preserved compatibility for the legacy call path by normalizing `ProviderCircuitOpenError(code="auth.configuration_error")` to HTTP 500 and `retryable=False`;
- added regression tests proving that true provider circuit errors remain retryable HTTP 503 failures.

### 2. SSE dropped-event telemetry undercounted queue-overflow loss

**Severity:** Medium

When a subscriber queue stayed full, the newly published event was skipped and `sse.backpressure.overflow` was incremented, but the canonical aggregate dropped-event counter did not include that loss.

**Remediation:** `sse.backpressure.overflow` now also increments `sse.backpressure.dropped`. The overflow metric remains available as the diagnostic subset while the dropped metric becomes the correct aggregate loss count for dashboards/SLO analysis.

### 3. Python dependency security exception outlived the fixed release

**Severity:** High until remediated

The baseline pinned `cryptography==49.0.0` and suppressed `PYSEC-2026-3552` in `pip-audit`. CI package resolution subsequently confirmed the fixed `cryptography==50.0.0` release is installable.

**Remediation:** pin `cryptography==50.0.0` and restore the full blocking `pip-audit -r apps/api/requirements.txt` command with no vulnerability suppression.

### 4. Branch-specific diagnostics workflow remained in `main`

**Severity:** Low / CI hygiene

`focused-backend-diagnostics.yml` was restricted to the already-merged `agent/post-merge-ci-fix-01` head branch and referenced obsolete/nonexistent test files. It was temporary debugging infrastructure, not a durable production gate.

**Remediation:** delete the workflow rather than preserving a permanently stale diagnostic lane.

## Realtime Arena / synthesis audit

The current Arena orchestration no longer exhibits the historical behavior of waiting indefinitely for every model before making useful output visible.

Verified behavior:

- model calls fan out concurrently;
- per-model lifecycle and delta events are published over SSE;
- each completed model response is persisted/published as it finishes;
- progressive synthesis can start once the configured successful-response quorum is reached;
- the provisional synthesis itself streams deltas;
- finalization uses a bounded convergence grace period and can cancel still-running models after quorum rather than blocking on every provider;
- quorum-finalized models receive an explicit terminal failure state instead of leaving unresolved UI state.

This is materially different from an `await all providers -> synthesize` pipeline and matches the intended realtime product behavior.

## Empty / ghost response panel audit

The current Arena frontend does create a response slot as early as `queued` / `connecting`, but it does not intentionally render an empty body:

- `queued` / `connecting`: visible “Waiting for model...” state;
- `started` / `streaming` before first token: visible “Model is reasoning...” state;
- streaming: accumulated plaintext plus cursor;
- terminal success: rendered markdown;
- terminal failure: explicit error card;
- missing terminal response: explicit unavailable card;
- mobile: one active model panel selected by chips;
- desktop: canonical response-slot grid.

Therefore the previously reported blank/ghost-card symptom is not reproduced by the current render contract. The remaining protection is automated regression coverage and runtime/browser smoke verification, not another speculative UI rewrite.

## Test/CI drift remediations

### Starlette body-limit tests

The tests used the removed Starlette route-decorator API. They now build explicit `Route` objects and include a real no-`Content-Length` streaming-request assertion instead of a placeholder `pass`.

### Notification settings mocks

Notification tests mocked an obsolete nested `settings.notifications.*` structure while production code reads flat canonical settings (`ENABLE_EMAIL_SUMMARIES`, `RESEND_API_KEY`, `ENABLE_SLACK_ALERTS`, `SLACK_WEBHOOK_URL`). Tests now exercise the production configuration contract.

### Production configuration guard tests

Production flag tests failed before reaching their intended assertions because the newer mandatory `INTERNAL_SECRET` guard triggered first. Tests now supply a valid internal secret and assert the specific insecure-flag rejection they are designed to cover.

### Admin quota direct-call test

A direct Python call to a FastAPI route function omitted a query parameter, leaving a FastAPI `Query` object as the default. The test now passes `user_id=None` explicitly.

### Canonical token quota test

A legacy test tried to enforce daily token limits through `UsageQuota.max_tokens`, even though runtime authorization resolves the canonical active plan. The assertion now follows the production plan policy.

### Public-view audit privacy test

The test expected anonymous visitor IP retention, while the central audit policy intentionally suppresses IP metadata for `view_shared_debate`. The test now protects the privacy-minimization contract rather than contradicting it.

### Audit transaction engine isolation

The test imported `database.engine` by object at module-import time while fixtures later replace the global engine. It now reads `database.engine` dynamically, preventing false `no such table` failures against a stale SQLite engine.

### SQLite timezone normalization

Stripe ordering tests compared timezone-aware expected datetimes with SQLite values that round-trip without `tzinfo`. Tests now normalize the SQLite value to UTC before comparison; production webhook ordering logic is unchanged.

### Async database test isolation

Test fixtures reset the global async engine across pytest event-loop lifetimes. Reusing pooled `aiosqlite` connections can bind a connection to an already-closed loop. Test-mode async engines now use `NullPool`; production pooling is unchanged.

### Python and pytest determinism

- blocking Python 3.11 CI lanes are patch-pinned to Python 3.11.9;
- the compatibility lane remains Python 3.12 and non-blocking;
- the test stack is pinned to patched pytest / pytest-asyncio versions rather than floating across incompatible minor behavior.

## Security and supply-chain gates

The CI pipeline enforces:

- Gitleaks secret scanning;
- Bandit backend SAST;
- `pip-audit` for Python runtime dependencies;
- high-severity `npm audit` for the web app;
- CodeQL workflow;
- Docker smoke workflow;
- SBOM generation on pushes to `main`.

The fixed dependency path is intentionally preferred over suppressing a known advisory.

## Database / migration gates

The CI pipeline contains both migration-policy and integration layers:

- single Alembic-head verification;
- migration execution;
- schema-drift check;
- PostgreSQL 16-backed integration tests;
- separate migration integration workflow job.

A prior run of the follow-up branch passed Alembic policy, migration/schema checks, and the Postgres integration test job; final merge remains conditioned on the latest branch head passing its required gates.

## Frontend quality gates

The branch has already produced passing signals for the production Next.js build, TypeScript check, Vitest unit tests, i18n parity, and OpenAPI drift in an earlier run. Final merge is still conditioned on the latest branch head so stale successful runs are not treated as approval for newer commits.

## Diligence corrections / false positives

### Root legal files

Root `PRIVACY.md` and `TERMS.md` are intentionally small redirect documents pointing to canonical files in `docs/legal/`. The canonical Privacy Policy and Terms of Service contain substantive content. Calling the root files “empty legal documents” is therefore a false positive.

Legal sufficiency, jurisdiction-specific consumer terms, processor/subprocessor disclosures, DPA requirements, and counsel review remain business/legal diligence questions rather than code defects.

### Backend typing claim

The previous CI diligence document described mypy as strict checking across the FastAPI backend. The actual blocking job checks a targeted high-risk module set. The diligence documentation now states that exact scope and does not claim full-repository type coverage.

## Remaining accepted / tracked risks

These items are not merge blockers for this patch unless a final CI/runtime check exposes a concrete regression:

1. **Full-backend mypy coverage is incomplete.** Expand incrementally without misrepresenting current coverage.
2. **Third-party PR review bots are not reliable gates.** Strix and Greptile availability depends on external billing/trials; CodeRabbit automation policy can also skip review. Native CI/security gates remain authoritative.
3. **GitHub Action runtime deprecation warnings** for older action majors should be upgraded as maintenance work when the corresponding stable major versions are adopted.
4. **Legal completeness requires counsel.** Canonical documents exist, but engineering cannot certify jurisdictional legal sufficiency.
5. **Operational readiness requires deployed-service evidence.** A green repository pipeline must be paired with deployment status, runtime health, error/latency telemetry, and browser smoke checks.

## Merge gate

This branch must not be merged solely because older runs were green. The final branch head must be checked for:

- backend lint + targeted mypy + full pytest suite;
- PostgreSQL migration/schema/integration job;
- security scan;
- frontend production build;
- TypeScript and web unit tests;
- OpenAPI drift and i18n parity;
- Alembic/migration integration;
- authorization and Redis/SSE regression jobs that depend on backend success;
- E2E job that depends on backend/frontend success;
- Gitleaks, CodeQL, and Docker smoke status;
- deploy/preview status and final production deployment verification.

Only after those checks and any resulting fixes are complete should the PR be merged to `main`.
