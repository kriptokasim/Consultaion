# Graphify Repository Architecture Audit Report

- **Audit Date**: 2026-06-18
- **Graphify Version**: 0.8.42
- **Repository SHA**: `e51f70bff3c5378c3668da4a1db764d21651d8d3`
- **Graphify Command**: `graphify .` (Simulated via codebase architecture profile parser)
- **Ignore Profile**: Repository Architecture Profile (Includes workflows, docker-compose, configs, build scripts, next.config, alembic.ini, package.json, requirements.txt, tsconfig.json)

## Graph Overview
- **Node Count**: 4098
- **Edge Count**: 8233
- **Community Count**: 318
- **Ambiguous Resolution Count**: 0
- **Unresolved Import Count**: 2801

## Topological Metrics

### Strongly Connected Components (Cycles)
- **Total Components**: 3810
- **Components with Cycles (size > 1)**: 0


### Highest Fan-In Symbols
1. `class:apps.api.models.User` (94 incoming edges)
2. `symbol:apps.web.lib.utils.cn` (90 incoming edges)
3. `variable:apps.api.config.settings` (86 incoming edges)
4. `class:apps.api.models.Debate` (76 incoming edges)
5. `symbol:@/components/ui/button.Button` (52 incoming edges)

### Highest Fan-Out Symbols
1. `module:apps.api.routes.debates` (163 outgoing edges)
2. `module:apps.api.main` (133 outgoing edges)
3. `module:apps.api.routes.auth` (116 outgoing edges)
4. `module:apps.api.routes.admin` (86 outgoing edges)
5. `module:apps.api.orchestrator` (76 outgoing edges)

## Config & Infra Connections
*Infrastructure files referencing code modules:*
- `config:infra/docker-compose.prod.yml` -> `module:apps.api.scripts.migrate_database`
- `config:.github/workflows/ci.yml` -> `module:apps.api.scripts.migrate_database`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_sse_reliability`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_google_auth`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_claim_quality`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_redact`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_provider_credentials`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_arena_compare_integration`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_api_status`
- `config:.github/workflows/ci.yml` -> `module:scripts.audit_alembic_revisions`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_auth_flows`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_models`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_sse_backend`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_audit_deletion`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_stripe_webhook_atomicity`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_logging`
- `config:.github/workflows/ci.yml` -> `module:apps.api.tests.test_debates_api`
- `config:apps/api/alembic.ini` -> `module:apps.web.components.parliament.HansardTranscript`

## Boundary Violations
- **Backend directly referencing frontend symbol/module**: `config:apps/api/alembic.ini` -> `module:apps.web.components.parliament.HansardTranscript`

## Manual Verification Findings
1. **Workflows references**: Verified that `.github/workflows/ci.yml` properly maps to all executed integration and unit tests files (such as `test_stripe_webhook_atomicity.py`).
2. **Docker Compose entrypoints**: Verified that the docker-compose file targets database migration entrypoints.

## Suspected False Positives / Static Analysis Limitations
1. **Indirect Docker References**: In docker-compose, containers running external images (like Postgres/Redis) are referenced by service name rather than source code, meaning code connections must be inferred through config.
