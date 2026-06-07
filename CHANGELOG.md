# Changelog

All notable changes to the **Consultaion** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
