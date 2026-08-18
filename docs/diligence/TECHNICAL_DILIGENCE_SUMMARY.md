# Consultaion Technical Diligence Summary

_Last reviewed: 2026-08-18_

## Executive summary

Consultaion is a multi-model AI decision platform with a Next.js frontend and FastAPI backend. The product supports model orchestration, Arena and Debate workflows, real-time Server-Sent Events, structured synthesis/reporting, BYOK credentials, usage/billing infrastructure, PostgreSQL persistence, Redis-backed runtime services, and automated security/quality gates.

The current technical foundation is suitable for pre-seed investor diligence and early strategic-acquirer review, provided the release candidate is presented from a clean, reproducible branch/tag and all required checks are green.

## Architecture

- Frontend: Next.js 15 / React 19
- Backend: FastAPI / Python
- Database: PostgreSQL with Alembic migrations
- Runtime services: Redis and Celery
- LLM routing: LiteLLM / OpenRouter plus direct providers
- Streaming: Server-Sent Events with per-model lifecycle events
- Authentication: JWT/cookie flows, Google OAuth, API-key support
- Billing: Stripe integration, plans, subscriptions, usage accounting
- Observability: Sentry/PostHog/Prometheus/OpenTelemetry/Langfuse surfaces documented in the repo

See `docs/ARCHITECTURE.md` for implementation detail.

## Core technical assets

### Multi-model orchestration

Consultaion does not depend on a single LLM provider. The model-gateway layer routes requests across multiple providers and supports user-owned credentials (BYOK). Arena runs multiple models in parallel and the reporting/synthesis layer produces a persistent decision artifact.

### Real-time execution

Arena and Debate execution publish lifecycle and response events through SSE. The current active hardening work in PR #49 targets replay safety, lifecycle monotonicity, reasoning-only activity handling, provider-health isolation, quorum finalization, and mobile rendering.

### Persistence and migrations

Business entities, run state, messages, billing records, usage, authentication data and related metadata are persisted through SQLModel/PostgreSQL. Alembic is used for migration history. Schema-drift checks are part of the repository quality strategy.

### Billing and unit-economics foundation

The codebase includes plan configuration, Stripe checkout/webhook handling, usage accounting and per-model token/cost surfaces. Investor-grade unit-economics reporting still needs to be consolidated into a single dashboard.

### Security controls

Existing controls and practices include:

- proprietary license
- secret scanning with Gitleaks
- SAST/dependency-audit workflows
- API/auth hardening
- provider-key protection/BYOK handling
- rate limiting and quotas
- security headers / CSP work
- documented secret-rotation process

These controls should be described as implemented engineering controls, not as formal compliance certification.

## Test and CI posture

The repository documents CI gates for linting, type checking, backend tests, Postgres integration tests, frontend/unit/E2E checks, OpenAPI drift and translation parity. Backend policy requires at least 75% statement coverage.

### Current diligence exception

As of 2026-08-18, PR #49 (`fix: harden realtime model lifecycle and mobile UX`) remains open and mergeable. Its head SHA is `e342ac1e5cb5d0b322ff3dbd44450de318128c50`.

GitHub reports four PR-triggered workflow runs with conclusion `action_required`:

- CI
- CodeQL
- Docker Smoke Test
- Gitleaks

The connector reports no jobs for the CI run, so this should **not** be represented as a test failure without additional evidence. It is a release-readiness blocker until the workflow-policy/approval state is resolved and the checks execute to a terminal success state.

## Investor/acquirer release gate

Do not present a technical release as diligence-ready until all of the following are true:

1. PR #49 is either merged after clean validation or intentionally closed/superseded.
2. Required GitHub Actions execute and are green.
3. Production smoke tests pass on the same release SHA.
4. Gitleaks and dependency audits are green.
5. No unresolved P0/P1 findings remain in the risk register.
6. The exact release SHA is tagged for diligence review.
7. Architecture, security, API and deployment docs match that release.

Recommended tag: `v1.0-investor-demo` once these gates are satisfied.

## Diligence strengths

- Product architecture is more mature than a typical prototype.
- Multi-provider/BYOK design reduces single-provider dependency.
- Real-time orchestration and synthesis create meaningful technical depth beyond a basic LLM wrapper.
- CI/security documentation and migration discipline improve auditability.
- Billing and usage primitives already exist, reducing the work needed to validate commercial economics.

## Diligence gaps

- A clean release candidate is not yet established.
- Investor KPI and unit-economics dashboards need to be made canonical.
- Enterprise IAM controls (for example SSO/SCIM/granular RBAC) remain roadmap items.
- Compliance documentation is readiness material, not a certification.
- The public-repository posture should be reviewed against the proprietary-IP strategy before broad diligence access.

## Recommended next technical milestones

1. Resolve PR #49 workflow state and produce a green release SHA.
2. Add canonical investor KPI + cost-per-run telemetry.
3. Add a release evidence bundle (test summary, dependency audit, secrets scan, deployment smoke result).
4. Add a formal open-source dependency/IP inventory.
5. Add Decision Graph persistence for assumptions, disagreements, risks, verdicts and follow-up outcomes.
