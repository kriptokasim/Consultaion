# Render Environment Variables

## Production Auth Configuration (Patchset 51.0)

Set these environment variables in your **Render dashboard** for the API service to enable cross-origin authentication with Vercel.

## Core Configuration

### Environment

```bash
ENV=production
```

**Important**: Render automatically sets `RENDER=true`. Do NOT set this manually.

### Frontend Origin

```bash
WEB_APP_ORIGIN=https://consultaion.vercel.app
CORS_ORIGINS=https://consultaion.vercel.app
```

Replace `consultaion.vercel.app` with your actual Vercel deployment URL.

### Auth Cookie Configuration

```bash
COOKIE_NAME=consultaion_session
```

**Auto-configured** (do not set manually):

- `COOKIE_SECURE=true` - Auto-set when `ENV=production`
- `COOKIE_SAMESITE=none` - Auto-set when running on Render

The system detects the Render environment via the `RENDER` env var and automatically configures secure, cross-site cookies.

## Required Security Settings

### JWT Secret

```bash
JWT_SECRET=<your-secure-random-string-32+-chars>
JWT_TTL_SECONDS=86400
```

**Critical**: Replace `<your-secure-random-string-32+-chars>` with a strong random string. Generate one with:

```bash
openssl rand -base64 32
```

### CSRF Protection

```bash
ENABLE_CSRF=1
CSRF_COOKIE_NAME=csrf_token
```

## Database

```bash
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:<port>/<database>
```

Use your Render PostgreSQL connection string.

## Google OAuth

### Required for Google Sign-In

```bash
GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<your-client-secret>
GOOGLE_REDIRECT_URL=https://consultaion.onrender.com/auth/google/callback
```

Replace `consultaion.onrender.com` with your actual Render service URL.

**Setup Steps**:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create OAuth 2.0 credentials
3. Add authorized redirect URI: `https://consultaion.onrender.com/auth/google/callback`
4. Copy Client ID and Client Secret to Render env vars

## Redis & Performance

### For Production (Recommended)

```bash
REDIS_URL=redis://<host>:<port>
RATE_LIMIT_BACKEND=redis
SSE_BACKEND=redis
```

Use Render's Redis addon or external Redis service.

### Alternative (Single Worker Only)

```bash
RATE_LIMIT_BACKEND=memory
SSE_BACKEND=memory
WEB_CONCURRENCY=1
```

**Note**: `WEB_CONCURRENCY=1` is the recommended default. Only increase if using Redis for SSE_BACKEND.

## Optional: Observability

### Sentry Error Tracking

```bash
SENTRY_DSN=<your-sentry-dsn>
SENTRY_ENV=production
SENTRY_SAMPLE_RATE=0.1
```

### Langfuse (LLM Observability)

```bash
LANGFUSE_PUBLIC_KEY=<your-public-key>
LANGFUSE_SECRET_KEY=<your-secret-key>
LANGFUSE_HOST=https://cloud.langfuse.com
```

### PostHog (Analytics)

```bash
POSTHOG_API_KEY=<your-api-key>
POSTHOG_HOST=https://app.posthog.com
```

## Optional: Billing & Integrations

### Stripe

```bash
STRIPE_SECRET_KEY=<your-stripe-secret-key>
STRIPE_WEBHOOK_SECRET=<your-webhook-secret>
STRIPE_PRICE_PRO_ID=<your-price-id>
BILLING_CHECKOUT_SUCCESS_URL=https://consultaion.vercel.app/settings/billing?status=success
BILLING_CHECKOUT_CANCEL_URL=https://consultaion.vercel.app/settings/billing?status=cancel
```

### N8N Automation

```bash
N8N_WEBHOOK_URL=<your-n8n-webhook-url>
```

## Complete Example

```bash
# Core
ENV=production

# Frontend
WEB_APP_ORIGIN=https://consultaion.vercel.app
CORS_ORIGINS=https://consultaion.vercel.app

# Auth
JWT_SECRET=your-super-secret-jwt-key-minimum-32-characters-long
JWT_TTL_SECONDS=86400
COOKIE_NAME=consultaion_session
ENABLE_CSRF=1

# Database
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/consultaion

# Google OAuth
GOOGLE_CLIENT_ID=123456789.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-secret
GOOGLE_REDIRECT_URL=https://consultaion.onrender.com/auth/google/callback

# Redis
REDIS_URL=redis://red-xyz123:6379
RATE_LIMIT_BACKEND=redis
SSE_BACKEND=redis

# LLM Providers (at least one required)
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...

# Sentry
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENV=production
```

## Verification

After setting environment variables and deploying:

1. **Check Auto-Configuration**:

   ```bash
   # SSH into Render or use logs
   python3 -c "from config import settings; print(f'COOKIE_SECURE: {settings.COOKIE_SECURE}'); print(f'COOKIE_SAMESITE: {settings.COOKIE_SAMESITE}'); print(f'IS_LOCAL_ENV: {settings.IS_LOCAL_ENV}')"
   ```

   Expected output:

   ```
   COOKIE_SECURE: True
   COOKIE_SAMESITE: none
   IS_LOCAL_ENV: False
   ```

2. **Test Auth Flow**:
   - Navigate to your Vercel URL and login
   - Check browser DevTools → Application → Cookies
   - Verify `consultaion_session` cookie exists for `consultaion.onrender.com`
   - Verify it has `Secure` and `SameSite=None` flags

## Troubleshooting

### Login Loop (Immediate Logout)

**Symptom**: Login succeeds briefly, then redirects back to login.

**Solution**:

1. Verify `WEB_APP_ORIGIN` matches your Vercel URL exactly
2. Verify `CORS_ORIGINS` includes your Vercel URL
3. Check cookie in browser DevTools - should show `SameSite=None; Secure`
4. Ensure `ENV=production` is set

### 401 Unauthorized on /me

**Symptom**: `/me` endpoint returns 401 after login.

**Solution**:

1. Cookie not being sent - verify `SameSite=None` in browser
2. CORS issue - verify `Access-Control-Allow-Credentials: true` header
3. Check Render logs for any error messages

### CSRF Token Errors

**Symptom**: POST requests fail with "CSRF token missing or invalid".

**Solution**:

1. Verify `ENABLE_CSRF=1` is set
2. Check that frontend is reading and sending `X-CSRF-Token` header
3. Ensure CSRF cookie uses same `SameSite` settings as auth cookie

## See Also

- [Vercel Environment Variables](./vercel-env-vars.md)
- [Local Development Setup](../README.md)
