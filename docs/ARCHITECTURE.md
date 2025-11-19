# Consultaion Architecture (Amber-Mocha)

Consultaion is a split repo containing a FastAPI backend (`apps/api`) and a Next.js App Router frontend (`apps/web`). The system orchestrates multi-LLM debates, billing, and team workflows while emitting events for downstream automations (n8n).

## High-level diagram
```
Browser ──▶ Next.js (Amber-Mocha UI)
              │
              ▼
        FastAPI (apps/api)
        │  ├─ auth, debates, stats, billing, promotions routers
        │  ├─ orchestrator (agents → judges → synthesis)
        │  └─ SSE channels (routes/common.CHANNELS)
        ▼
  Postgres + Alembic schema
        │      ├─ debates, rounds, messages, scores, votes
        │      ├─ billing_plans, billing_subscriptions, billing_usage
        │      ├─ promotions, audit_log, usage counters/quotas
        │      └─ auth users, teams, API keys
        ▼
   Redis (optional) for rate limiting / SSE fan-out
```

LLM access goes through LiteLLM, which can speak to OpenAI, Anthropic, OpenRouter, Gemini, etc. The registry (`model_registry.py`) loads configs from env vars, flags the recommended model, and powers `/models` as well as the orchestrator’s model selection.

## Debate pipeline
1. User calls `POST /debates`. `routes/debates.py` persists the record, enforces quotas (`reserve_run_slot`), increments billing usage, and enqueues an SSE channel.
2. `orchestrator.run_debate` loads the `DebateConfig`, spawns agents (`produce_candidate`), runs cross critiques, judges, and synthesizer, then writes back to Postgres (rounds, messages, scores, votes, final meta).
3. Token usage per model is aggregated through `UsageAccumulator` and recorded via `billing.service.add_tokens_usage`, feeding `/billing/usage/models` for the Amber billing UI.
4. SSE consumers stream from `CHANNELS[debate_id]` and receive `round_started`, `message`, `score`, `notice`, and `final` events. Stale channels are swept using `CHANNEL_TTL_SECS`.

## Billing subsystem
- Tables: `billing_plans`, `billing_subscriptions`, `billing_usage`, `promotions`.
- `billing/service.py` resolves the active plan, tracks debates/exports/tokens, and raises 402 errors when limits are exceeded. Usage events trigger n8n webhooks (`integrations/events.py`).
- Stripe skeleton (`billing/providers/stripe_provider.py`) returns placeholder checkout URLs until real keys are provided. Future providers (Iyzico, manual invoicing) will plug into the same interface.

## Promotions & n8n
`promotions` table stores contextual upsell modules. The frontend drops `<PromotionArea location="dashboard_sidebar" />` or `"debate_limit_modal"` depending on the view. When usage nears 80% or a subscription activates, the backend emits lightweight events to `N8N_WEBHOOK_URL`, enabling Slack/Notion automations.

## Security & compliance
- Cookie-based JWT auth with optional double-submit CSRF and strict security headers (`ENABLE_SEC_HEADERS`).
- IP rate limiting (memory or Redis backend) plus per-user hourly and daily quotas in `usage_limits.py`.
- Google OAuth flow sanitizes the `next` parameter and enforces HTTPS origins in production.
- Prompt safety: `agents.build_messages()` adds a defensive system message that guards against instruction injection. Mock mode can be left on for development (`USE_MOCK=1`), but production deployments should set `USE_MOCK=0` and `REQUIRE_REAL_LLM=1`.

## Frontend integration
- `/pricing` renders plan limits from `/billing/plans`.
- `/settings/billing` fetches both `/billing/me` and `/billing/usage/models`, renders usage bars, and hands upgrades to `/billing/checkout`.
- Billing limit modals intercept 402 responses (debate creation, exports) and surface targeted promotions.
- Dashboard SSE client consumes `/debates/{id}/stream` and displays the Hansard transcript, Voting Chamber, and Amber-Mocha analytics cards.

## Testing
`pytest -q` covers auth, debates, orchestrator helpers, billing, promotions, usage tracking, migrations, goog auth, SSE, rate limits, and the model registry. The new audit-derived suites live in `apps/api/tests/test_orchestrator.py`, `test_ratings.py`, `test_rate_limits.py`, `test_sse.py`, and expanded `test_models.py`.
