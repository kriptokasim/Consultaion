# Consultaion Operations Runbook

## Overview

This runbook provides operational guidance for running Consultaion in production.

---

## Health Checks

### Endpoints

**`GET /healthz`**

- Basic health check
- Returns `200 OK` if service is running
- No authentication required

**`GET /readyz`**

- Readiness check (includes DB, Redis, SSE backend)
- Returns `200 OK` if all dependencies are healthy
- Use for load balancer health checks

**Expected Response:**

```json
{
  "status": "healthy",
  "database": "ok",
  "redis": "ok",
  "sse_backend": "ok"
}
```

**If Unhealthy:**

1. Check logs for errors
2. Verify DATABASE_URL is accessible
3. Verify REDIS_URL is accessible (production)
4. Check server resources (CPU, memory, disk)

---

## Deployments & Rollbacks

### Deployment Process

**Backend (Render):**

1. Push to `main` branch triggers auto-deploy
2. Render builds from `apps/api/`
3. Runs migrations automatically (Alembic)
4. Redeploys with zero-downtime

**Frontend (Vercel):**

1. Push to `main` branch triggers auto-deploy
2. Vercel builds from `apps/web/`
3. Deploys to production URL
4. Automatic preview deployments for PRs

### Rollback Procedure

**Render Rollback:**

1. Navigate to Render dashboard → Service → "Manual Deploy"
2. Select previous successful deployment
3. Click "Deploy"
4. Verify `/healthz` returns 200

**Vercel Rollback:**

1. Navigate to Vercel dashboard → Deployments
2. Find last known good deployment
3. Click "..." → "Promote to Production"
4. Verify site loads correctly

**Emergency Rollback (Git):**

```bash
git revert <commit-hash>
git push origin main
```

---

## Incident Handling

### Where to Look First

**1. Admin Events Console**

- URL: `/admin/events`
- Filter by severity: `error`, `warning`
- Check last 24 hours

**2. External Monitoring**

- **Sentry**: Error tracking and tracing
- **Langfuse**: LLM call traces and token usage
- **PostHog**: User analytics and feature usage

**3. Server Logs**

- Render: Dashboard → Logs
- Check for rate limit errors, database errors, LLM failures

### Common Issues

**Issue: Rate Limit Exceeded**

- **Symptom**: Users getting `429 Too Many Requests`
- **Check**: `/admin/ops/summary` → recent_429 events
- **Fix**: Temporary - increase rate limits in config, Long-term - upgrade user plan

**Issue: Database Connection Errors**

- **Symptom**: `readyz` fails, 500 errors
- **Check**: DATABASE_URL environment variable, database server status
- **Fix**: Restart service, verify connection string, check database server

**Issue: Model Provider Failures**

- **Symptom**: Debates fail with "circuit_open" errors
- **Check**: `/admin/ops/summary` → provider_health
- **Fix**: Wait for circuit cooldown (60s default), verify API keys, check provider status pages

### Disabling Non-Core Features

If a feature is causing issues, disable via environment variables:

```bash
# Render dashboard → Environment → Add/Edit
ENABLE_CONVERSATION_MODE=false
ENABLE_GIPHY=false
ENABLE_EMAIL_SUMMARIES=false
ENABLE_SLACK_ALERTS=false
```

After changing, trigger a redeploy for changes to take effect.

---

## Quotas & Billing

### Viewing User Usage

**Admin Usage Overview:**

```
GET /admin/usage?email=user@example.com
```

Returns:

- Current period: tokens, exports, debates
- Last 7 days: totals
- Plan details

### Adjusting Quotas

**Default Quotas (config.py):**

- `DEFAULT_MAX_RUNS_PER_HOUR`: 30
- `DEFAULT_MAX_TOKENS_PER_DAY`: 150,000

**To change:**

1. Update `apps/api/config.py`
2. Commit and push
3. Auto-deploys to production

**Per-User Quotas:**

- Managed via `BillingPlan` model
- Update plan limits in database or admin panel
- Changes take effect immediately

### Monitoring Usage Patterns

**High Token Users:**

```sql
SELECT user_id, SUM(tokens_used) as total
FROM billing_usage
WHERE period >= '2025-12'
GROUP BY user_id
ORDER BY total DESC
LIMIT 10;
```

---

## Monitoring Stack

### Langfuse (LLM Observability)

**Purpose:** Track LLM calls, token usage, traces

**Check Health:**

- Visit Langfuse dashboard
- Verify traces are recent (< 5 min)
- Check for errors in traces

**Environment Variables:**

- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST`
- `ENABLE_LANGFUSE=1`

### PostHog (Analytics)

**Purpose:** User behavior, feature usage, events

**Key Events:**

- `debate_started`, `debate_completed`
- `conversation_started`, `conversation_completed`
- `template_used`, `model_modal_opened`

**Environment Variables:**

- `NEXT_PUBLIC_POSTHOG_API_KEY` (frontend)
- `NEXT_PUBLIC_POSTHOG_HOST`

### Sentry (Error Tracking)

**Purpose:** Exception monitoring, performance tracking

**Environment Variables:**

- `SENTRY_DSN`
- `SENTRY_ENV` (production/staging)
- `SENTRY_SAMPLE_RATE` (0.1 = 10%)

---

## Rate Limits Reference

### Production Limits

- General API: **60 requests/min**
- Debate Creation: **10 requests/min**
- Authentication: **10 requests/5min**

### Development Limits

- General API: **300 requests/min**
- Debate Creation: **50 requests/min**
- Authentication: **50 requests/5min**

Limits are automatically set based on `ENV` variable.

---

## Quick Commands

**Check Recent Errors:**

```bash
# Via API
curl https://api.consultaion.app/admin/events?level=error \
  -H "Cookie: consultaion_token=..."
```

**Test Slack Alerts:**

```bash
# Via Admin Panel
POST /admin/test-alert
```

**View System Health:**

```bash
curl https://api.consultaion.app/readyz
```

---

## Emergency Contacts

- **Infrastructure**: Render support, Vercel support
- **Monitoring**: Sentry dashboard, Langfuse dashboard
- **Database**: Check Render database logs

---

**Last Updated:** December 2025 (Patchset 54.0)
