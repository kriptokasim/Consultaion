# Delivery status

**As of:** 2026-08-28 UTC
**Revision inspected:** `e35186f542d7d37fe2c1491d207cab9d9112ac25` on the supplied `work` branch. The checkout is shallow and has no configured remote or local `main` ref, so remote notification details cannot be independently fetched here.

## Incident finding

The OpenRouter “no request” symptom is a deterministic routing/credential regression, not evidence of an OpenRouter outage. Key-isolation hardening removed ambient key export, but gateway calls still passed only BYOK/request keys. With an OpenRouter-only deployment, Arena registry filtering hid direct-provider seats; if a seat remained, streaming resolved its canonical direct provider, passed `api_key=None`, and had no streaming fallback. Structured Debate could select a direct adapter and likewise omit its server key; its eventual OpenRouter fallback also omitted the OpenRouter key. Execution therefore failed locally before a valid OpenRouter HTTP request could be made.

The regression predates merge `4d6524c0`: history identifies the explicit-key change in `ba0d8b8`/`e75dff4` (PS155). Merge `4d6524c0` added execution fencing/error sanitization and preserved the already-broken gateway behavior; it is the visible hardening boundary, not the originating gateway diff. Follow-up `e35186f` supplies matching server keys explicitly, enables Arena seats reachable through OpenRouter, adds pre-delta streaming fallback, and preserves non-streaming fallback model identity.

## Provider branches

- Mock/test: `MockAdapter`; no network.
- OpenRouter-native target: `OpenRouterAdapter` directly with user/request/server OpenRouter credential.
- Direct target: user BYOK, explicit request key, then server provider key; `DirectProviderAdapter` first.
- Direct failure or missing direct key: OpenRouter fallback only when its server key exists and its circuit is closed. Streaming fallback is allowed only while content is empty.
- No usable key/circuit open: deterministic `missing_provider_key` or `no_healthy_provider_route`; no provider request is expected.

## Job/evidence matrix

The referenced 2026-08-24 notification payloads and Actions logs are not present in the checkout. Consequently, claiming exact historical conclusions for “every failing job” would be fabricated. The workflow defines these independently failing jobs: URL scan/theme, i18n, full URL scan (push only), security scan (gitleaks/Bandit/pip-audit/npm audit), SBOM (push only), backend, PostgreSQL backend, OpenAPI drift, compatibility, frontend, and E2E jobs. Exact historical step/error evidence remains an external GitHub access blocker.

Local evidence:
- `pytest -q --no-cov tests/test_model_gateway.py` equivalent assertions passed: 8 tests passed. Running without `--no-cov` exits nonzero solely because a focused selection cannot meet the global 75% coverage threshold.
- A complete pytest attempt under the pre-existing Python 3.14 root environment was stopped after systemic failures. Representative deterministic failures were async connections using a separate SQLite database (`sqlite3.OperationalError: no such table: debate`) and an SSE readiness assertion expecting the wrapped backend rather than `TerminalCommitGuard`. Python 3.14 is outside the CI baseline and this is not accepted as CI reproduction.
- Root repository lint could not start because root dependencies are absent and `npx` received `403 Forbidden` from the package registry. This is an environment/package-access blocker, not a source-code result.

## Milestone state

| Milestone | State | Evidence / blocker |
|---|---|---|
| M0 setup/evidence | **In progress** | Setup script repaired for repository paths and supported versions; Python 3.11.15 is available through pyenv, but bootstrap correctly rejects the active Node 24 runtime because CI requires Node 20. Root npm installation is additionally blocked by a registry 403. GitHub logs unavailable. |
| M1 provider routing | **Locally verified, pending supported-runtime suite** | Focused gateway assertions pass; `e35186f` contains the safe fix and mocks. |
| M2 backend/database | **Blocked** | Supported Python 3.11 and PostgreSQL service not available; complete Python 3.14 attempt exposed failures but is not production-equivalent. |
| M3 frontend/contracts | **Blocked** | `apps/web/node_modules` exists: ESLint, TypeScript, all 392 Vitest tests, and the production build pass under the available Node 24 runtime. Node 20 parity and root guards remain blocked; root dependencies are absent and the registry returns 403. |
| M4 packaged runtime | **Not started** | Sequential exit rule: M2/M3 are not green. |
| M5 production | **Externally blocked** | No OpenRouter, Render, Vercel, GitHub, production test-user credentials/URLs or account access supplied. No billing/account changes attempted. |

## External blockers and next executable milestone

External: retrieve the named GitHub Actions run logs; activate the available Python 3.11.15 together with a Node 20 runtime, provide package-registry access, Docker/PostgreSQL/Redis, and approved production credentials/URLs. Credentials must be injected, never shared in chat or committed.

Next executable milestone is M0: run `PYTHON_BIN=python3.11 scripts/setup.sh`, retain the Actions job logs, then execute the M1 focused command. Only after M1 is green should M2 begin.
