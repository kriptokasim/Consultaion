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
        │  └─ SSE backend (memory or Redis via `sse_backend.py`)
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

## Configuration

Runtime configuration is centralized in `apps/api/config.py`, which exposes a Pydantic `AppSettings` instance. Every service (FastAPI app, rate limiter, SSE backend, auth, billing, etc.) imports from this module instead of reading `os.getenv` directly. This keeps type hints consistent, enforces sane defaults, and allows tests to reload settings deterministically when they override environment variables.

## Debate pipeline
1. User calls `POST /debates`. `routes/debates.py` persists the record, enforces quotas (`reserve_run_slot`), increments billing usage, and registers an SSE channel through `sse_backend.get_sse_backend()`.
2. `orchestrator.run_debate` loads the `DebateConfig`, spawns agents (`produce_candidate`), runs cross critiques, judges, and synthesizer, then writes back to Postgres (rounds, messages, scores, votes, final meta).
3. Token usage per model is aggregated through `UsageAccumulator` and recorded via `billing.service.add_tokens_usage`, feeding `/billing/usage/models` for the Amber billing UI.
4. SSE consumers subscribe to `/debates/{debate_id}/stream`, which forwards events from the configured backend (in-memory queues by default, Redis pub/sub in multi-worker mode).

Parliament seat outputs are now **structured JSON**: prompts instruct each seat to emit `{"content": "...", "reasoning": "...", "stance": "..."}` only. The engine parses this into `SeatLLMEnvelope`/`SeatMessage` models (with fallbacks to raw text) and publishes `seat_message` SSE events containing seat metadata (role, provider, model, stance) so downstream consumers and replay tools can rely on consistent shapes.

LLM reliability now runs through a single retry/backoff helper (configurable via `LLM_RETRY_*` in `AppSettings`). Debate rounds track per-seat failures; when the failure ratio or minimum-seat threshold is breached, the parliament engine emits a `debate_failed` SSE event and returns a `FAILED` status instead of limping along with low-quality output.

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
