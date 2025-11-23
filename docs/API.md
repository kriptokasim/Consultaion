# Consultaion API – Amber-Mocha v0.4

Backend origin: `http://localhost:8000` in development. All endpoints return JSON and rely on cookie-based JWT auth unless stated otherwise. Swagger (`/docs`) and ReDoc (`/redoc`) remain enabled for ad‑hoc inspection, but this document tracks the canonical behaviour tested in CI.

## Authentication

### Email/password
- `POST /auth/register` → `{ "email", "password" }`. Validates length, enforces unique email, and sets the auth cookie on success.
- `POST /auth/login` → `{ "email", "password" }`. Uses the same cookie; 401 JSON payload `{ "detail": "invalid credentials" }` on failure.
- `POST /auth/logout` clears cookies.
- `GET /auth/me` returns `{ id, email, role }` for the current user.

All unsafe requests require the `X-CSRF-Token` header whose value must match the `csrf_token` cookie when `ENABLE_CSRF=1`.

### Google OAuth
- `GET /auth/google/login?next=/dashboard` issues a redirect to Google with a signed `state` value and the `WEB_APP_ORIGIN` + `/auth/google/callback` redirect.
- `GET /auth/google/callback?...` validates the `state`, exchanges the code via Google’s token endpoint, and redirects the browser to `next` (default `/dashboard`). Only same-origin `next` values are accepted.

## Debates & Runs
- `POST /debates` launches a debate: `{ prompt, model_id?, config? }`. `config` is a `DebateConfig` (agents, judges, budget). Responses contain the debate id.
- `GET /debates?status=completed&limit=20&offset=0&q=climate` returns a paginated list (items, total, limit, offset, has_more). The payload is scoped to the authenticated user unless they are an admin.
- `GET /debates/{id}` returns full debate metadata for authorized users.
- `POST /debates/{id}/export` and `GET /debates/{id}/scores.csv` both increment billing export usage and return either Markdown or CSV.
- `GET /debates/{id}/stream` exposes the SSE feed (Amber UI uses it for the live Hansard view). Events include `round_started`, `message`, `score`, `notice`, `final`, and `error`. SSE responses set `Cache-Control: no-store` and stream until completion or timeout.

## Models & Registry
- `GET /models` lists enabled models with provider, tags, max context, and `recommended` flag. The registry inspects provider API keys (OpenAI, Anthropic, OpenRouter, Gemini, etc.) at startup; disabled providers never appear.
- `GET /models/{id}` (via stats router) yields extended metadata including win rates and last-seen timestamps.

## Billing
- `GET /billing/plans` → `{ "items": [{ slug, name, price_monthly, currency, is_default_free, limits }] }`.
- `GET /billing/me` returns `{ plan, usage }` for the authenticated user. `usage` surfaces `period`, `debates_created`, `exports_count`, and `tokens_used`.
- `POST /billing/checkout` expects `{ "plan_slug": "pro" }`. Uses the configured provider (Stripe placeholder by default) and responds with `{ "checkout_url": "https://..." }`.
- `POST /billing/webhook/stripe` accepts unsigned JSON while running locally and hands it to the provider skeleton.
- `GET /billing/usage/models` aggregates `{ model_id, display_name, tokens_used, approx_cost_usd }` for the current period; the Amber-Mocha settings/billing page consumes this endpoint.

**Billing errors:** Quota enforcement raises HTTP 402 with payloads such as:
```json
{
  "detail": {
    "code": "BILLING_LIMIT_DEBATES",
    "max": 10
  }
}
```
Callers should redirect users to `/pricing` or `/settings/billing` when they see a 402 response.

## Promotions
- `GET /promotions?location=dashboard_sidebar` returns `{ "items": [{ id, title, body, cta_label?, cta_url? }] }`. Anonymous users only receive generic promos; authenticated users additionally receive rows targeting their current plan (`target_plan_slug`). Locations currently used: `dashboard_sidebar`, `billing_sidebar`, and `debate_limit_modal`.

## Automations & Events
The backend emits lightweight JSON webhooks to `N8N_WEBHOOK_URL` via `integrations/events.py`. Events include `subscription_activated`, `usage_limit_nearing` (fires at 80% of debate quota), and `usage_limit_exceeded`.

## Rate limiting & quotas
- IP burst limits use `increment_ip_bucket(ip, RL_WINDOW, RL_MAX_CALLS)`. When exceeded, `/auth/login` and `/debates` return 429 with `{ "detail": "rate limit exceeded" }` and a `Retry-After` header.
- User quotas: `reserve_run_slot` enforces hourly run counts, `record_token_usage` tracks daily tokens. Violations raise `RateLimitError` and bubble up as 429 with payload `{ "code": "runs_per_hour", "detail": "Hourly run quota exceeded", "reset_at": "2025-11-20T00:00:00Z" }`.

## Error payloads
Errors follow the [RFC 7807](https://www.rfc-editor.org/rfc/rfc7807) style when possible:
```json
{
  "detail": "debate not found"
}
```
or for structured billing/rate errors:
```json
{
  "detail": {
    "code": "tokens_per_day",
    "detail": "Daily token quota exceeded",
    "reset_at": "2025-11-20T00:00:00Z"
  }
}
```

## Testing notes
- Set `USE_MOCK=1 FAST_DEBATE=1` to exercise the mocked debate path without calling external LLMs.
- The pytest suite covers `auth`, `debates`, `billing`, `promotions`, orchestrator helpers, ratings, rate limits, SSE channel hygiene, and the model registry.

## Operations
- LLM reliability knobs live in `LLM_RETRY_*` settings; increase delays/attempts if providers are rate limiting.
- Debate failure tolerance is controlled by `DEBATE_MAX_SEAT_FAIL_RATIO`, `DEBATE_MIN_REQUIRED_SEATS`, and `DEBATE_FAIL_FAST`. When thresholds are breached, debates are marked failed and emit a `debate_failed` SSE event.
