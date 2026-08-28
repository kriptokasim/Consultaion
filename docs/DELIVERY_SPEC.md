# Production delivery specification

## Objective

Complete the existing Consultaion SaaS without replacing its FastAPI, Celery, Redis/PostgreSQL, model-gateway, or Next.js architecture. Completion requires deterministic repository gates and credentialed production evidence. Secrets must never appear in logs or commits.

## Milestones and acceptance criteria

### M0 — reproducible toolchain and incident evidence

Acceptance:
- clean bootstrap uses Python 3.11 and Node 20;
- the current revision and the `4d6524c0` merge ancestry are recorded;
- each CI job is classified as deterministic, infrastructure, or credential/account dependent;
- failure claims link to retained command/run evidence rather than inference.

Validation: `bash -n scripts/setup.sh`; `PYTHON_BIN=python3.11 scripts/setup.sh`; `git log --oneline --decorate -15`.

### M1 — provider routing recovery

Acceptance:
- OpenRouter-only configuration exposes the complete Arena panel;
- server credentials are explicitly passed after key-isolation hardening;
- Arena streaming attempts OpenRouter when a direct key is absent or the direct call fails before emitting text;
- Structured Debate non-streaming fallback preserves the requested model identity;
- deterministic tests prove direct preference, missing-key fallback, failure fallback, and OpenRouter-only routing without network calls.

Validation: `cd apps/api && pytest -q --no-cov tests/test_model_gateway.py tests/test_model_target_resolver.py tests/test_gateway_integration.py tests/test_debate_pipeline_integration.py tests/test_core_engine_recovery.py`.

### M2 — backend and database

Acceptance: Ruff and the CI mypy slice pass; the complete pytest suite meets its coverage threshold; PostgreSQL 16 migrations reach the single Alembic head; schema drift and the PostgreSQL integration slice pass.

Validation commands are the `backend-test` and `backend-postgres-test` commands in `.github/workflows/ci.yml`, plus `bash scripts/check-alembic-heads.sh` and `bash scripts/check-schema-drift.sh`.

### M3 — frontend and contract

Acceptance: URL/color/i18n guards, ESLint, TypeScript, Vitest, Next production build, and OpenAPI drift pass under Node 20.

Validation: `npm run lint:urls`; `npm run lint:colors`; `npm run lint:i18n`; `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`; `./scripts/check_openapi_drift.sh`.

### M4 — packaged runtime

Acceptance: Docker smoke starts the web/API/worker dependencies, API readiness passes, Celery is responsive, and Redis-backed SSE publishes and resumes events.

Validation: `bash scripts/smoke-docker.sh`; `python scripts/smoke-production-sse.py --help` followed by the credential-free local invocation documented in `docs/E2E_SMOKE.md`.

### M5 — production verification

Acceptance: Render web and Celery worker are healthy, migrations are current, real OpenRouter smoke succeeds, real Arena and Structured Debate reach durable terminal success, Redis SSE is observed, Vercel is healthy, and no unresolved P0/P1 security finding remains.

Validation: `npx tsx scripts/prod_smoke.ts` with approved URLs; `bash scripts/smoke-production-run.sh` with an approved test identity; Render/Vercel/GitHub deployment evidence and the admin LLM smoke response. This milestone requires credentials and is never simulated.
