# Continuous Integration Overview

This document provides a summary of the Continuous Integration (CI) pipeline implemented for Consultaion via GitHub Actions.

## Canonical Development Environment

All code integrations, pull requests, automated testing, and release configurations are executed and tracked on GitHub.

## CI Workflows & Quality Gates

The primary workflow is configured in `.github/workflows/ci.yml`. It runs automatically on pull requests and commits to the `main` branch.

### 1. Code Quality & Formatting
- **Linter & Formatter**: We use `ruff` to enforce styling, import sorting, and code quality patterns across the backend repository.
- **Type Checker**: We use `mypy` to enforce strict type checking on the FastAPI backend code.

### 2. Secrets Scan
- **Gitleaks**: Every pull request is audited for committed secrets (API keys, private keys, certificates). The secrets scan is a **blocking gate**; if any secret signature is detected, the build immediately fails.

### 3. Backend Test Suite (SQLite)
- A fast backend test suite runs against a local SQLite database to verify general business logic, routes, and unit behaviors.

### 4. Integration Test Suite (Postgres)
- A dedicated, Postgres-backed integration test suite executes database migrations using Alembic and runs integration tests against a live PostgreSQL service container (matching the production PostgreSQL version).
- **Alembic Migration Guard**: A validation step automatically ensures that there are no diverging Alembic migration heads.

### 5. Frontend & E2E Validation
- Builds the Next.js production bundle.
- Runs Vitest component unit tests.
- Runs Playwright E2E and accessibility smoke tests.

### 6. OpenAPI Schema Verification
- A verification script generates the OpenAPI specification from the current state of the FastAPI routers and compares it to `docs/openapi.json`. Any undocumented API drifts fail the pipeline.

### 7. Translation Parity
- A custom script (`scripts/check_i18n_parity.js`) asserts that keys match between English and Turkish translation bundles.
