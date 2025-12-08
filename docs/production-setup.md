# Production Setup Guide – Consultaion

## Overview

This guide covers deploying and configuring Consultaion in production using:

- **API**: FastAPI on Render
- **Web**: Next.js on Vercel

---

## Prerequisites

- Render account (for API deployment)
- Vercel account (for web deployment)
- PostgreSQL database (Render provides this)
- Redis instance (optional but recommended for production)
- LLM provider API keys (OpenAI, Anthropic, or Google)

---

## 1. API Deployment (Render)

### 1.1. Create Web Service

1. Connect your GitHub repository to Render
2. Create a new **Web Service**
3. Configure:
   - **Name**: `consultaion-api` (or your preference)
   - **Environment**: Python 3
   - **Build Command**: Use Render's auto-detect or specify if needed
   - **Start Command**: `gunicorn main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
   - **Root Directory**: `apps/api`

### 1.2. Environment Variables

Add the following environment variables in Render dashboard:

#### Required

```bash
# Environment
ENV=production

# Database (use Render PostgreSQL)
DATABASE_URL=<from Render PostgreSQL addon>

# Security
JWT_SECRET=<generate 64-char random string>
# Example: openssl rand -hex 32

# Web App Origin
WEB_APP_ORIGIN=https://consultaion.vercel.app
CORS_ORIGINS=https://consultaion.vercel.app

# At least one LLM provider
OPENAI_API_KEY=sk-...
# OR
ANTHROPIC_API_KEY=sk-ant-...
# OR
GEMINI_API_KEY=...
```

#### Recommended

```bash
# Redis (for rate limiting + SSE)
REDIS_URL=<from Render Redis addon>
RATE_LIMIT_BACKEND=redis
SSE_BACKEND=redis

# OAuth (Google Sign-In)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URL=https://consultaion.onrender.com/auth/google/callback

# Observability
SENTRY_DSN=...
SENTRY_ENV=production
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
ENABLE_LANGFUSE=1

# PostHog (optional server-side)
POSTHOG_API_KEY=...
ENABLE_POSTHOG=1
```

#### Optional

```bash
# Features
ENABLE_CONVERSATION_MODE=0
ENABLE_GIPHY=1
GIPHY_API_KEY=...

# Notifications
ENABLE_SLACK_ALERTS=1
SLACK_WEBHOOK_URL=...
ENABLE_EMAIL_SUMMARIES=1
RESEND_API_KEY=...

# Billing
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
```

### 1.3. Health Check Configuration

- **Health Check Path**: `/healthz`
- **Health Check Interval**: 30 seconds
- **Failure Threshold**: 3

---

## 2. Web Deployment (Vercel)

### 2.1. Create Project

1. Import your GitHub repository
2. Configure:
   - **Framework Preset**: Next.js
   - **Root Directory**: `apps/web`
   - **Build Command**: `npm run build` (auto-detected)
   - **Install Command**: `npm install` (auto-detected)

### 2.2. Environment Variables

Add in Vercel dashboard (Settings → Environment Variables):

#### Required

```bash
# Environment
NEXT_PUBLIC_APP_ENV=production

# API URL
NEXT_PUBLIC_API_URL=https://consultaion.onrender.com
```

#### Recommended

```bash
# PostHog Analytics
NEXT_PUBLIC_POSTHOG_API_KEY=phc_...
NEXT_PUBLIC_POSTHOG_HOST=https://app.posthog.com

# Sentry (optional)
NEXT_PUBLIC_SENTRY_DSN=...
SENTRY_ORG=...
SENTRY_PROJECT=...
```

### 2.3. Build Configuration

Vercel auto-detects Next.js. No special build config needed.

---

## 3. Database Setup

### 3.1. Render PostgreSQL

1. Create PostgreSQL addon in Render
2. Copy `Internal Database URL` to `DATABASE_URL` env var
3. Run migrations (done automatically on API startup)

### 3.2. Redis (Optional but Recommended)

1. Create Redis addon in Render
2. Copy `Internal Redis URL` to `REDIS_URL` env var
3. Set `RATE_LIMIT_BACKEND=redis` and `SSE_BACKEND=redis`

---

## 4. Verification Checklist

After deployment, verify:

### API Health

```bash
curl https://consultaion.onrender.com/healthz
# Expected: {"status":"ok","version":"1.0.0"}

curl https://consultaion.onrender.com/readyz
# Expected: {"db":"ok","models_available":true,...}
```

### Web Health

```bash
curl https://consultaion.vercel.app/healthz
# Expected: {"status":"ok","env":"production",...}
```

### CORS Configuration

```bash
# Test from browser console on vercel app:
fetch('https://consultaion.onrender.com/me', {credentials: 'include'})
# Should not have CORS errors
```

### Environment Detection

- API `/healthz` should show `version`
- Web `/healthz` should show `"env":"production"`
- Telemetry (Sentry/PostHog) should only initialize in production

### Rate Limits

```bash
# Verify production rate limits are active (60/min, not 300/min)
curl https://consultaion.onrender.com/stats/rate-limit
# Should show: {"window":60,"max_calls":60,...}
```

---

## 5. Monitoring & Alerts

### Health Monitoring

- Render provides built-in uptime monitoring
- Set up external monitoring (e.g., UptimeRobot, Better Uptime):
  - API: `https://consultaion.onrender.com/healthz`
  - Web: `https://consultaion.vercel.app/healthz`

### Error Tracking

- **Sentry**: Monitor exceptions and performance
  - API: Initialized automatically when `SENTRY_DSN` is set
  - Web: Added via Next.js Sentry integration

### Analytics

- **PostHog**: User behavior and feature usage
  - Web: Only initializes when `NEXT_PUBLIC_APP_ENV=production`
- **Langfuse**: LLM call traces and token usage
  - API: Only when `ENABLE_LANGFUSE=1`

### Slack Alerts (Optional)

- Set `ENABLE_SLACK_ALERTS=1` and `SLACK_WEBHOOK_URL`
- Test: `curl -X POST https://consultaion.onrender.com/admin/test-alert`

---

## 6. Scaling Considerations

### API Scaling

- Render auto-scales based on your plan
- For better performance:
  - Use Redis for SSE and rate limiting
  - Increase `GUNICORN_WORKERS` (default: 2x CPU cores)
  - Consider horizontal scaling with load balancer

### Database

- Render PostgreSQL auto-backs up
- Monitor connection pool:
  - `DB_POOL_SIZE=10` (default)
  - `DB_MAX_OVERFLOW=20`

### Rate Limits

- Production limits are strict: 60 req/min, 10 debate creation/min
- Adjust `PROD_RL_MAX_CALLS` and `PROD_RL_DEBATE_CREATE_MAX_CALLS` based on usage

---

## 7. Security Checklist

- [ ] `JWT_SECRET` is 32+ characters and secure
- [ ] `ENV=production` is set
- [ ] CORS origins are explicitly set (no wildcards)
- [ ] `COOKIE_SECURE=true` (automatic in production)
- [ ] `COOKIE_SAMESITE=none` for cross-domain (automatic)
- [ ] `ENABLE_CSRF=1`
- [ ] `ENABLE_SEC_HEADERS=1`
- [ ] All API keys are set via environment variables (not in code)
- [ ] `.env` files are in `.gitignore`

---

## 8. Rollback Procedure

### API Rollback (Render)

1. Go to Render dashboard → Services → consultaion-api
2. Navigate to "Manual Deploy" tab
3. Select previous successful deployment
4. Click "Deploy"

### Web Rollback (Vercel)

1. Go to Vercel dashboard → Deployments
2. Find last known good deployment
3. Click "..." → "Promote to Production"

### Database Rollback

- If migrations fail:
  - SSH into Render shell (if available)
  - Run: `alembic downgrade -1`
- Better: Test migrations in staging first

---

## 9. Staging Environment (Optional)

To set up staging:

1. **API**: Create second Render service with `ENV=staging`
2. **Web**: Use Vercel preview deployments or separate project
3. Use separate database and Redis instances
4. Set `NEXT_PUBLIC_APP_ENV=staging` for web

---

## 10. Common Issues

### Issue: CORS errors in production

**Symptoms**: API calls fail with CORS errors

**Fix**:

- Verify `WEB_APP_ORIGIN` matches Vercel URL exactly
- Verify `CORS_ORIGINS` includes Vercel URL
- Check cookies: `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none`

### Issue: Debates timeout

**Symptoms**: Debate creation fails or hangs

**Fix**:

- Check `LLM_TIMEOUT_SECONDS` (default: 30)
- Verify LLM API keys are valid
- Check Render logs for provider errors
- Increase timeout if needed: `LLM_TIMEOUT_SECONDS=60`

### Issue: Rate limit too strict

**Symptoms**: Users get 429 errors frequently

**Fix**:

- Adjust production limits:
  - `PROD_RL_MAX_CALLS` (default: 60)
  - `PROD_RL_DEBATE_CREATE_MAX_CALLS` (default: 10)

### Issue: Health check failing

**Symptoms**: Render shows service as unhealthy

**Fix**:

- Check `/readyz` endpoint: may be database or model config issue
- Ensure at least one LLM provider key is set
- Verify database connection

---

## 11. Post-Deployment Tasks

1. **Test critical flows**:
   - Google OAuth sign-in
   - Create debate (real, not demo)
   - Export debate to PDF
   - View hall of fame

2. **Verify telemetry**:
   - Check Sentry for any errors
   - Verify PostHog events are flowing
   - Check Langfuse traces for LLM calls

3. **Monitor for 24h**:
   - Watch Render metrics (CPU, memory)
   - Check error rates in Sentry
   - Review rate limit stats: `/stats/rate-limit`

4. **Update DNS** (if using custom domain):
   - Point API domain to Render
   - Point web domain to Vercel

---

**Last Updated**: December 2025 (Patchset 54.0)

For operational guidance, see `docs/ops/runbook.md`.
