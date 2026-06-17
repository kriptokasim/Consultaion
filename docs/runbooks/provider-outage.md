# Provider Outage Runbook

When one or more LLM providers are degraded or down, follow this checklist to diagnose, mitigate, and recover.

---

## 1. Confirm the Outage

### Check provider circuit state
```bash
curl -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/v1/ops/providers/readiness
```

Look for:
- `circuit_state: "open"` — circuit breaker tripped, provider is being skipped
- `consecutive_failures` — how many recent failures
- `last_failure` — timestamp and error message

### Probe individual providers
```bash
curl -X POST -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/v1/ops/providers/openai/probe
```

Each probe returns latency and error classification. Check all configured providers.

---

## 2. Identify Root Cause

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| `invalid_credentials` | API key expired or rotated | Rotate key in `.env`, redeploy |
| `insufficient_balance` | Provider credits exhausted | Top up account, or enable fallback providers |
| `rate_limit_exceeded` | Too many concurrent calls | Wait for cooldown (auto-opens after 60s), or reduce concurrency |
| `model_timeout` | Provider-side latency | Check provider status page; may resolve automatically |
| `api_error` (5xx) | Provider outage | Wait for provider recovery; circuit will auto-close |

---

## 3. Mitigate

### If a single provider is down
- The circuit breaker already routes around it — no action needed unless ALL providers are affected
- Run a probe to verify: `POST /api/v1/ops/providers/{provider}/probe`

### If multiple providers are down
1. Check OpenRouter as fallback (routes through their infrastructure)
2. Check Redis connectivity: `redis-cli ping` — circuit state lives in Redis
3. If Redis is down, circuits fail open (all providers are attempted)

### If all providers are down
1. Verify API keys are still valid (check provider dashboards)
2. Check for network issues: `curl -I https://api.openai.com`
3. Check the diagnostic endpoint for the affected run:
   ```bash
   curl -H "Authorization: Bearer <admin_token>" \
     http://localhost:8000/api/v1/ops/debates/{debate_id}/diagnostics
   ```

---

## 4. Verify Recovery

1. Probe each provider: `POST /api/v1/ops/providers/{provider}/probe`
2. Check circuit state returns to `closed`
3. Create a test run and verify responses arrive
4. Check worker heartbeats are flowing: `GET /api/v1/ops/providers/readiness` → `workers` array

---

## 5. Post-Incident

- Review `LLMUsageLog` for failure patterns
- Check if circuit breaker thresholds need tuning in `config.py`:
  - `PROVIDER_HEALTH_COOLDOWN_SECONDS` (default 60s)
  - `PROVIDER_HEALTH_MIN_CALLS` (default 3)
- If provider keys were rotated, verify all services (API + worker) picked up new keys
