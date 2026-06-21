# Run Pipeline Deployment Guide

This guide covers the minimum production environment required for Debate/Arena runs to actually execute and reach real LLM providers.

## Why OpenRouter Dashboard Shows Zero Usage

If the OpenRouter dashboard shows no API usage after creating debates, the request is likely not reaching the provider layer at all. Common causes:

1. **Autorun disabled** — `DISABLE_AUTORUN=true` creates queued runs that never start
2. **No worker** — Celery dispatch mode requires a running worker process
3. **Memory broker** — `CELERY_BROKER_URL=memory://` loses tasks on process restart
4. **Missing API key** — `OPENROUTER_API_KEY` not set in backend environment
5. **No models enabled** — No provider keys means no models in the registry

Use the diagnostics to identify which step is broken:

```bash
# Check pipeline health
curl -H "Authorization: Bearer <admin-token>" https://your-app/run-pipeline-health

# Run LLM smoke test
curl -X POST -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"provider": "openrouter"}' \
  https://your-app/ops/llm-smoke-test
```

## Required Backend Environment

### Core Settings

```bash
# Environment detection
ENV=production

# Database
DATABASE_URL=postgresql://...

# Security (required in production)
JWT_SECRET=<64-char random string>
INTERNAL_SECRET=<64-char random string>
```

### LLM Provider Keys

At least one provider key is required. OpenRouter provides access to multiple models:

```bash
# Primary provider (recommended)
OPENROUTER_API_KEY=sk-or-v1-...

# Optional direct providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
GROQ_API_KEY=gsk_...
MISTRAL_API_KEY=...
```

### Run Pipeline Settings

```bash
# Autorun must be enabled for runs to execute automatically
DISABLE_AUTORUN=false

# Require real LLM calls (no mock mode in production)
REQUIRE_REAL_LLM=true
USE_MOCK=false
```

## Celery Mode (Recommended for Production)

Celery mode offloads debate orchestration to a separate worker process, preventing long-running debates from blocking web request handlers.

### Configuration

```bash
DEBATE_DISPATCH_MODE=celery
CELERY_BROKER_URL=redis://<redis-host>:6379/0
CELERY_RESULT_BACKEND=redis://<redis-host>:6379/0
```

### Starting the Worker

```bash
cd apps/api
celery -A worker.celery_app.celery_app worker \
  -Q interactive,maintenance,default \
  --loglevel=INFO \
  --concurrency=4
```

### Verifying Worker Health

After deployment, check that the worker heartbeat is visible:

```bash
curl -H "Authorization: Bearer <admin-token>" \
  https://your-app/ops/run-pipeline-health | jq '.worker'
```

The response should show `"heartbeat_seen": true` with a recent `last_heartbeat_age_seconds`.

## Inline Mode (Development Only)

Inline mode executes debates directly in the web request handler. This is simpler but blocks the web worker during long debates.

```bash
DEBATE_DISPATCH_MODE=inline
```

**Warning:** Inline mode is not recommended for production. Long-running debates will block web workers and may cause request timeouts.

## SSE Configuration

Server-Sent Events require Redis in production with multiple workers:

```bash
SSE_BACKEND=redis
SSE_REDIS_URL=redis://<redis-host>:6379/0
```

## Running the Smoke Test

After deployment, verify end-to-end execution:

```bash
# Generate admin token (or use existing)
# Run the smoke test script
python scripts/smoke_run_pipeline.py \
  --base-url https://your-app.onrender.com \
  --token <admin-jwt-token> \
  --provider openrouter
```

Expected output on success:

```
Run Pipeline Smoke Test
==================================================

[1/4] Checking pipeline health...
  pipeline health: ok
  blocking errors: 0
  warnings: 0
  worker heartbeat: seen
  openrouter key: present

[2/4] Running LLM smoke test...
  llm smoke: success, provider=openrouter, latency=842ms

[3/4] Creating test debate...
  debate id: <uuid>
  autorun: True
  dispatch_mode: celery
  queue: interactive

[4/4] Polling debate status (max 300s)...
  status: running (elapsed: 5.2s)
  status: completed (elapsed: 12.1s)

==================================================
PASS (4 checks passed)
```

## Diagnostics Endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /ops/run-pipeline-health` | Admin | Full pipeline health check |
| `POST /ops/llm-smoke-test` | Admin | Prove provider reachability |
| `GET /ops/debates/{id}/diagnostics` | Admin | Per-debate diagnostics |
| `GET /ops/providers/readiness` | Admin | Provider circuit state |

All diagnostic endpoints hide secret values. Only booleans like `key_present: true/false` are exposed.

## Troubleshooting

### "Autorun is disabled" warning

Set `DISABLE_AUTORUN=false` in your environment variables.

### "No healthy worker heartbeat detected"

Ensure the Celery worker is running and `CELERY_BROKER_URL` points to a real Redis instance (not `memory://`).

### "OPENROUTER_API_KEY is missing"

Add `OPENROUTER_API_KEY=sk-or-v1-...` to your backend environment variables.

### "CELERY_BROKER_URL resolves to memory://"

Set `CELERY_BROKER_URL=redis://<host>:6379/0` pointing to a real Redis instance.

### Debate stuck in "queued"

Check the stale cleanup is running. Debates queued longer than `DEBATE_STALE_QUEUED_SECONDS` (default 1800s) are automatically marked as failed with reason `run_dispatch_timeout`.
