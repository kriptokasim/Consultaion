# Improvement Plan (Audit 14.x)

| Item | Priority | Status | Notes |
| --- | --- | --- | --- |
| Harden Google OAuth redirect handling | P0 | ✅ Completed in v0.4 (Patchset 13.x) | `routes/auth.py` now sanitizes `next` + state. |
| Enforce unique JWT secret & CSRF defaults | P0 | ✅ Completed | README + runtime guard prevent default secrets. |
| Rate limit + quota instrumentation | P0 | ✅ Completed | Memory/Redis buckets + hourly/daily quotas tested in `test_rate_limits.py`. |
| Multi-LLM registry & mock/real toggles | P1 | ✅ Completed | Registry powers `/models`, `_call_llm` honours provider overrides. |
| Billing schema + plan enforcement | P1 | ✅ Completed in 14.2A/B | Alembic migration (`fb386f1f3bb4`), `/billing/*` endpoints, Amber UI wiring. |
| Promotions + n8n events | P1 | ✅ Completed in 14.2C | `/promotions` router + `integrations/events.py` + docs. |
| Orchestrator integration tests | P1 | ⚙️ In progress | Helper/fast-path tests merged; full loop tests blocked by long-running LiteLLM mocks. |
| SSE lifecycle & cleanup tests | P1 | ✅ Completed | `test_sse.py` covers channel creation/cleanup/TTL. |
| Architect & API docs | P2 | ✅ Completed in 14.3 | Added `docs/API.md` and `docs/ARCHITECTURE.md`. |
| Improvement summary / tracking doc | P2 | ✅ Completed | See `IMPROVEMENTS_SUMMARY.md`. |

Legend: ✅ = merged; ⚙️ = partial/test gaps; ⏳ = scheduled.
