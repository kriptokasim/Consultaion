# Delivery plan

| Order | Milestone | Work | Exit rule |
|---|---|---|---|
| 0 | Reproduction | Bootstrap supported runtimes; capture local and Actions evidence; classify failures. | M0 commands pass and evidence gaps are explicit. |
| 1 | Provider recovery | Audit Arena and Structured Debate call graphs; retain the smallest gateway/key/fallback fix; add mocks. | M1 focused suite passes. |
| 2 | Backend/database | Resolve complete pytest, Ruff, mypy, Alembic, schema drift, and PostgreSQL failures. | Every M2 command passes; no skipped required gate. |
| 3 | Frontend/contracts | Resolve repository guards, lint, typecheck, unit tests, build, and OpenAPI drift. | Every M3 command passes. |
| 4 | Runtime | Verify Docker, worker, Redis, readiness, and SSE resume semantics. | Every M4 check passes locally. |
| 5 | Production | Run approved, minimal-cost provider and end-to-end smokes; verify deployments and security. | Credentialed evidence satisfies all M5 criteria. |

Milestones are sequential: a later milestone may be investigated, but is not marked complete while an earlier milestone has a deterministic failure. External blockers do not prevent work on independent deterministic gates.

## Provider call graph under verification

Arena: `orchestrator.run_debate` selects `arena.engine.run_arena`; each panel seat calls `model_gateway.route_llm_stream`; `resolve_model_target` identifies the canonical direct provider; a user BYOK key is preferred, then the matching server key; before any delta, an unavailable/failing direct route can call `OpenRouterAdapter.stream_llm` with the OpenRouter server key.

Structured Debate: `orchestrator.run_debate` selects the canonical parliament engine; parliament providers bridge to `model_gateway.route_llm_call`; routing strategy selects mock, OpenRouter, or direct; credentials resolve as user BYOK, request key, then matching server key; an unsuccessful direct chain can call `OpenRouterAdapter.call_llm` with the OpenRouter server key.

Fallback is forbidden after streamed content because joining answers from different providers would corrupt the Arena response.
