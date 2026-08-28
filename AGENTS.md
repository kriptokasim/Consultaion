# Consultaion delivery instructions

## Scope
These instructions apply to the entire repository.

## Architecture and safety
- Preserve the existing FastAPI/Celery/Next.js architecture; prefer focused fixes and regression tests.
- Never print, persist, or commit provider, deployment, database, or signing credentials.
- Provider-routing tests must use mocks. A real-provider smoke is an explicit, separately reported production check.
- Treat `apps/api/model_gateway` as the sole outbound model-routing boundary for Arena and Structured Debate.

## Supported toolchain
- Python 3.11 is the CI and production baseline.
- Node.js 20 is the frontend and repository-tooling baseline.
- Use `scripts/setup.sh` from the repository root for a clean local bootstrap.

## Validation
- Do not describe a partial test selection as the complete suite.
- Record environmental and account blockers separately from deterministic failures.
- Update `docs/DELIVERY_STATUS.md` with the exact command and outcome when a delivery milestone changes state.
- Never bypass Alembic head, schema-drift, security, lint, type, test, or build gates to make CI green.
