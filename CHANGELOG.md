# Changelog


## Patchset 135
- **Production Readiness**: `internal_beta`
- **Verified Code SHA**: `ef0acf74afed34caeeaee291a13481713eb932ee`
- Closed Tracks: 0, A, C
- Open Tracks: E_backend, E_frontend, E3, D

All notable changes to the **Consultaion** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-06-16

### Added
- **FH39: Immutable Continuation Attempts**: Terminal states (completed/failed/cancelled/paused) have empty transition sets; UNIQUE(debate_id, idempotency_key) constraint; FK retry_of_continuation_id.
- **FH40: Continuation Contract and Recovery Loop**: Frontend stores continuation_id; mount-based recovery from localStorage; duplicate-action protection.
- **FH41: Real Schema Drift**: Script validates schema drift via compare_metadata(); migration parity tests check revision lengths, chain uniqueness, single head.
- **FH42: Trusted Rate-Limit Identity**: Validates cookie JWT and API keys; respects TRUSTED_PROXY_CIDRS; bounded cache.
- **FH43: SSE Concurrent Stream Limiter**: Lease-based limiter via Redis sorted sets; HTTP 503 on limit reached; configurable max streams per debate.
- **FH44: Report Provenance**: DecisionReportView renders FallbackResponseCard/UnstructuredSynthesisCard/ReportGenerationFailedCard without fabricated data.
- **FH45: Feature Flags Wiring**: FeatureGate wired in RunDetailClient for unifiedWorkspace, mobileWorkspaceV2, stagedDecisionPipelinePublic; /config/features endpoint enriched.
- **FH46: ReconciliationWindow + Cost Reconciliation**: New ReconciliationWindow dataclass; versioned model pricing; cost comparison vs recorded totals; removed legacy period helpers.
- **FH47: Celery Beat + Redis Locking**: crontab() schedules; deterministic run key per window; Redis distributed lock preventing duplicate executions.
- **FH48: Docker Compose Fixes**: Root-relative paths; test-safe env; psycopg driver; correct startup ordering; smoke script fixes.
- **FH49: Observability Wiring**: Continuation transition metrics; pipeline stage duration/failure metrics; synthesis/verification result counters; conditional console exporter.

### Changed
- Reconciliation uses datetime-based window boundaries instead of string period parsing.
- Celery beat schedules use proper crontab() objects.
- billing_tasks.py uses window-based run keys with Redis locking.
- Console span exporter only activates in dev/test/smoke environments.

### Fixed
- Docker compose paths corrected to root-relative context.
- Smoke script assertions use proper health checks (no subshell read).
- SSE reconnection tracking via SSE_RECONNECTS_TOTAL metric.
- Period_end not exported for legacy period helpers (removed).

## [0.2.0] - 2026-06-07

### Added
- **API Versioning Strategy**: Introduced `/api/v1` APIRouter namespace mapping all domain endpoints to allow versioned API support.
- **OpenAPI Schema Publishing**: Created automated OpenAPI export script (`scripts/export_openapi.py`) and published `docs/openapi.json`.
- **Stripe Webhook Idempotency**: Added a new database table `BillingWebhookEvent` and implemented deduplication/check logic inside the Stripe webhook handler.
- **Rate-Limit Fingerprinting**: Upgraded rate limiter to use composite request fingerprint hash based on `IP`, `User-Agent`, and `Accept-Language` headers.
- **Repository Pattern Pilot**: Created `DebateRepository` class pattern for data access isolation and refactored GET `/debates/{debate_id}` to use it.
- **Boot-time JWT Secret Checks**: Implemented JWT secret key strength checks at server startup in production and staging environments to enforce at least 32 characters and non-default fallback values.
- **Enhanced Multi-Tenancy & Isolation documentation**: Detailed the project's security boundaries in `docs/multi-tenancy.md` and backpressure/queuing strategies in `docs/queue-backpressure.md`.
- **Python Compatibility analysis**: Formally documented the ASGI TestClient POST request thread deadlock symptoms and pins in `docs/python-compatibility.md`.
- **Frontend Test Expansion**: Added Vitest test suites under `apps/web` to expand coverage for client wrappers, helpers, and components.

### Fixed
- **N+1 Queries**: Optimized admin endpoints `admin_users` and `admin_usage_overview` by prefetching and bulk-mapping plan subscriptions, active plans, and billing usage counters in-memory.
- **Git Repo Hygiene**: Cleaned up cache paths and configured `.gitignore` to omit `.mypy_cache/` and `.ruff_cache/` folders.

---

## [0.1.0] - 2026-06-07

### Added
- **Live Metrics Dashboard**: Added `/admin/metrics` endpoint supporting DAUs, active debates, shared debate views, plan counts, and economics/LLM costs calculation.
- **API Key Expiration warning**: Implemented key expiration/rotation scanner running periodically inside lifetime lifespan events.
- **Enhanced Marketing Methodology**: Redesigned methodology page featuring B2B Executive Summary on 360° Risk Analysis and Unbiased Decision Support.
- **Stripe Webhook verification**: Upgraded Stripe webhook processing safety and resolved timezone parsing in assertions.
- **Redis Connection Pooling**: Integrated shared client pooling in `redis_pool.py`.
