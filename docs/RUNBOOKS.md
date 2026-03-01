# Backend Operations Runbook

This document provides minimal troubleshooting procedures for common backend incidents on the Consultaion application.

## 1. Stuck "Running" Debates

**Symptom:** A debate stays in the "running" state indefinitely, and users see a spinner that never resolves.
**Cause:** The worker process crashed, OOM killed, or experienced a hard fault before it could release the DB lease or mark the debate as `failed`.
**Resolution:**

1. Check the `debates` table in Postgres for records where `status = 'running'` and `lease_expires_at` is in the past.
2. The orchestrator is designed to auto-recover these if `run_attempt` is low enough. If it's stuck, manually set `status = 'failed'` and empty `runner_id`.

```sql
UPDATE debates SET status = 'failed', final_meta = '{"error": "Manual intervention: stuck lease"}'
WHERE status = 'running' AND lease_expires_at < NOW();
```

## 2. SSE Missing Events / Connect Failures

**Symptom:** UI says "Debate is running..." but no events appear, then suddenly it completes.
**Cause:** In a multi-worker setup, if `SSE_BACKEND=memory` is accidentally used, publishers and subscribers might hit different processes. Alternatively, Redis is down.
**Resolution:**

1. Ensure `SSE_BACKEND=redis` in `.env.production`. The application will refuse to boot with `memory` and >1 workers now.
2. Check Redis connectivity.
3. If Redis is down, SSE Degraded metrics (`sse.publish.degraded` / `sse.publish.failed`) will spike. The application will continue running the debate but the UI will have to fall back to polling the timeline endpoint.

## 3. Circuit Breaker Open (TransientLLMError / ProviderCircuitOpenError)

**Symptom:** Spikes in `debate.degraded` metrics and Slack alerts for "transient/provider failure".
**Cause:** LLM provider (OpenAI / Anthropic / Gemini) is experiencing an outage or we are hitting severe rate limits (429s).
**Resolution:**

1. We have fallback providers configured via OpenRouter. If OpenRouter itself is down, the Circuit Breaker trips.
2. If it's an isolated provider, routing should automatically switch.
3. Check Sentry for the underlying 5xx/429 errors from the LLM provider to confirm an external outage. No code changes required; it will auto-recover when the provider recovers.

## 4. Configuration Boot Failures

**Symptom:** Application containers crash loop on startup.
**Cause:** Patchset 107 introduced strict startup validation for production.
**Resolution:**
Check the runtime logs. You will explicitly see `FATAL: Refusing startup in production/staging...`
Validations enforced:

- `USE_MOCK` must be `False`
- `REQUIRE_REAL_LLM` must be `True`
- `ENABLE_SEC_HEADERS` must be `True`
- `ENABLE_CSRF` should be `True`
Update the `.env` file for the deployment to satisfy these guardrails.

## 5. Database Connection Exhaustion

**Symptom:** `TimeoutError` getting connection from SQLAlchemy pool.
**Resolution:**

1. Ensure no rogue scripts are holding transactions open.
2. Verify `max_overflow` and `pool_size` in `config.py` are sufficient for the number of concurrent Uvicorn workers. (Default is pool=10, overflow=20 per process).
