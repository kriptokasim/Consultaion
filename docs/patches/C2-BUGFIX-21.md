# C2-BUGFIX-21 — Realtime Model Lifecycle Hardening

This patch hardens Arena and Debate execution, streaming lifecycle correctness, BYOK isolation, mobile rendering, and dependency security.

## Runtime corrections

- Provider health now isolates user-owned BYOK credential failures from shared provider circuits.
- Debate attributes calls to the effective seat model and skips retries for deterministic credential/model errors.
- Reasoning-only provider chunks count as activity without exposing hidden reasoning content.
- Arena finalizes after quorum and persists explicit terminal states for cancelled late models.
- Debate can complete with warnings when minimum successful-seat requirements are met.
- SSE model and synthesis lifecycle reducers are monotonic and replay-safe.

## Frontend and validation

- Model and synthesis deltas are validated with Zod before reducer dispatch.
- Mobile Arena cards are compact and display a clear reasoning-in-progress state.
- Playwright includes real WebKit plus 320 px and 430 px mobile viewports.
- Backend and frontend security dependencies were refreshed and OpenAPI drift was reconciled.

## Verification

Focused backend tests, Ruff, mypy, Python 3.12 compatibility checks, TypeScript, Vitest, npm audit, pip-audit, production frontend build, OpenAPI drift checks, Gitleaks, and schema checks cover this change set.
