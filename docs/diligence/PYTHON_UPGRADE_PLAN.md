# Python 3.12 Upgrade Roadmap

This document outlines the strategy, checklist, and rollout plan for upgrading the Consultaion API backend runtime from Python 3.11 to Python 3.12.

## Background and Rationale
Upgrading to Python 3.12 brings substantial performance enhancements (including faster interpreter startup, improvements to async/await performance, and optimized dictionary lookups) as well as access to the latest security patches and language features (improved generic types syntax, f-string improvements, and better error messages).

## Key Risks & Dependencies
1. **Async Postgres Driver (`psycopg` / `asyncpg`):** Must verify compatibility of the binary packages with Python 3.12.
2. **FastAPI & SQLModel:** Need to ensure runtime stability and Pydantic v2 compatibility.
3. **C-extensions & Third-party Libraries:** Ensure all binary wheels are pre-built or compile successfully in standard Python 3.12 Docker images.

---

## Migration Checklist & Milestones

### Phase 1: Local & CI Validation (Milestone: Q3 2026)
- [x] Configure non-blocking Python 3.12 CI job to run tests on every pull request.
- [ ] Monitor Python 3.12 test results in CI and resolve any deprecation warnings or compatibility issues.
- [ ] Upgrade local development setups to Python 3.12 and gather developer feedback.

### Phase 2: Dependency & Build Hardening (Milestone: Q4 2026)
- [ ] Update `Dockerfile` to build from `python:3.12-slim` in a sandbox branch.
- [ ] Resolve any compilation errors or missing wheels during dependency installation.
- [ ] Run full E2E Playwright test suite against Python 3.12 dev environment.

### Phase 3: Rollout & Deployment (Milestone: Q4 2026)
- [ ] **Staging Verification:** Deploy the Python 3.12 backend docker image to Render staging environment. Run synthetic load tests.
- [ ] **Canary Rollout:** Deploy Python 3.12 to 10% of production traffic using Render's canary rollout or blue-green deployment.
- [ ] **Monitoring & Alerting:** Closely monitor Sentry error rates, CPU/Memory utilization, and request latency.
- [ ] **Full Promotion:** Promote Python 3.12 to 100% of production traffic once stability is verified.
