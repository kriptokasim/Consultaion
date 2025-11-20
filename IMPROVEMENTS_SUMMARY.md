# Improvements Summary (Amber-Mocha audit)

- **Multi-LLM routing**: Model registry autodetects OpenAI, Anthropic, Gemini, and OpenRouter keys; `/models` exposes the catalog and orchestrator honours user-selected `model_id`.
- **Billing core**: Plans, subscriptions, monthly usage, and promotions tables are live. `/billing/me`, `/billing/plans`, `/billing/checkout`, `/billing/usage/models`, and `/promotions` feed the new Amber-Mocha pricing + billing UI. 402 responses now carry structured codes.
- **Usage enforcement**: Debate creation, exports, and orchestrator token accounting call into `billing.service` and `usage_limits.py`. n8n receives `subscription_activated`, `usage_limit_nearing`, and `usage_limit_exceeded` events.
- **Orchestrator hardening**: Safety wrappers (`build_messages`), audit logging, and helper tests lock in ranking/budget logic. FAST mode remains available for smoke tests, while the main path captures per-model usage.
- **Rate limits**: Memory/Redis backends plus hourly/daily quotas now have direct pytest coverage (`test_rate_limits.py`). 429 events are recorded for diagnostics.
- **SSE resilience**: Streaming now uses a pluggable backend (`MemoryChannelBackend` or Redis), exercised via `sse_backend.py` and covered with backend + route tests.
- **Docs**: `docs/API.md` and `docs/ARCHITECTURE.md` describe the current B2C SaaS stack, including Google OAuth, billing flows, promotions, and automations. README links to both for onboarding.
- **Improvement tracking**: `IMPROVEMENT_PLAN.md` captures audit items, priority, and completion status so future releases can pick up remaining TODOs.
