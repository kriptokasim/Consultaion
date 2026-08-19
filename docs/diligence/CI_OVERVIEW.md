# Continuous Integration Overview

This document provides a summary of the Continuous Integration (CI) pipeline implemented for Consultaion via GitHub Actions.

## Canonical Development Environment

All code integrations, pull requests, automated testing, and release configurations are executed and tracked on GitHub.

## CI Workflows & Quality Gates

The primary workflow is configured in `.github/workflows/ci.yml`. It runs automatically on pull requests and commits to the `main` branch.

### 1. Code Quality & Formatting
- **Linter & Formatter**: We use `ruff` to enforce styling, import sorting, and code quality patterns across the backend repository.
- **Type Checker**: `mypy` is a blocking targeted gate for the highest-risk typed backend modules (`services/usage_ledger.py`, `billing/service.py`, `billing/providers/stripe_provider.py`, and `guards/llm_action_guard.py`). Full-repository mypy coverage is not yet claimed; expanding the typed surface is tracked as technical-debt reduction rather than represented as an existing gate.

### 2. Secrets & Dependency Scanning
- **Gitleaks**: Every pull request is audited for committed secrets (API keys, private keys, certificates). The secrets scan is a blocking gate.
- **Bandit**: Backend Python source is scanned for medium/high-confidence security issues.
- **pip-audit / npm audit**: Runtime Python and high-severity Node dependency advisories are blocking CI checks.

### 3. Backend Test Suite (SQLite)
- The backend test suite runs against an isolated SQLite test database to verify business logic, routes, authorization, billing, orchestration, SSE behavior, and unit-level contracts.
- Python 3.11 CI is patch-pinned for deterministic execution; a separate non-blocking Python 3.12 compatibility lane provides forward-compatibility signal.

### 4. Integration Test Suite (Postgres)
- A dedicated Postgres-backed integration suite executes database migrations using Alembic and runs integration tests against a live PostgreSQL 16 service container.
- **Alembic Migration Guard**: Validation ensures there are no diverging migration heads and checks migration/schema drift before merge.

### 5. Frontend & E2E Validation
- Builds the Next.js production bundle.
- Runs TypeScript type checking and Vitest unit tests.
- Runs Playwright E2E validation after the backend and frontend build gates succeed.

### 6. OpenAPI Schema Verification
- A verification script generates the OpenAPI specification from the current FastAPI routers and compares it to `docs/openapi.json`. Undocumented API drift fails the pipeline.

### 7. Translation Parity
- A custom script (`scripts/check_i18n_parity.js`) asserts that keys match between English and Turkish translation bundles.

## Diligence Interpretation

A green workflow means the checks explicitly configured above passed for that commit. It should not be interpreted as proof that every source file is fully statically typed or that operational reliability is guaranteed without deployment/runtime monitoring. This document intentionally describes the implemented gates rather than aspirational coverage.
