# Vercel Environment Variables

## Production Frontend Configuration (Patchset 51.0)

Set these environment variables in your **Vercel project settings** to enable cross-origin authentication with Render.

## Required Configuration

### API Backend URL

```bash
NEXT_PUBLIC_API_URL=https://consultaion.onrender.com
```

Replace `consultaion.onrender.com` with your actual Render API service URL.

**Important**:

- Do NOT include a trailing slash
- Must use `https://` in production
- Must be a `NEXT_PUBLIC_` variable to be available in the browser

## Optional Features

### Conversation Mode

```bash
NEXT_PUBLIC_ENABLE_CONVERSATION_MODE=1
```

Enables the new conversation mode feature in the UI.

### PostHog Analytics

```bash
NEXT_PUBLIC_ENABLE_POSTHOG=1
```

Enables PostHog analytics tracking (requires PostHog setup on backend).

### Sentry Error Tracking

```bash
NEXT_PUBLIC_SENTRY_DSN=https://...@sentry.io/...
```

Enables frontend error tracking with Sentry.

## Complete Example

```bash
# Required
NEXT_PUBLIC_API_URL=https://consultaion.onrender.com

# Optional Features
NEXT_PUBLIC_ENABLE_CONVERSATION_MODE=1
NEXT_PUBLIC_ENABLE_POSTHOG=1

# Optional Monitoring
NEXT_PUBLIC_SENTRY_DSN=https://abc123@o456789.ingest.sentry.io/1234567
```

## Deployment Environments

Vercel supports environment-specific variables:

### Production

Set for **Production** deployment:

```bash
NEXT_PUBLIC_API_URL=https://consultaion.onrender.com
```

### Preview

Set for **Preview** deployments (PR previews):

```bash
NEXT_PUBLIC_API_URL=https://consultaion-staging.onrender.com
```

### Development

Set for **Development** (local):

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## How to Set Variables in Vercel

1. Go to your project in [Vercel Dashboard](https://vercel.com/dashboard)
2. Navigate to **Settings** → **Environment Variables**
3. Add each variable:
   - **Key**: Variable name (e.g., `NEXT_PUBLIC_API_URL`)
   - **Value**: Variable value (e.g., `https://consultaion.onrender.com`)
   - **Environment**: Select `Production`, `Preview`, and/or `Development`
4. Click **Save**
5. **Redeploy** your application for changes to take effect

## Verification

After deployment:

1. **Check Variable is Set**:
   - Open browser DevTools → Console
   - Run: `console.log(process.env.NEXT_PUBLIC_API_URL)`
   - Should show your Render URL

2. **Test API Connection**:
   - Navigate to your Vercel URL
   - Open Network tab in DevTools
   - Look for requests to your API URL
   - Verify requests include `Cookie` header with `consultaion_session`

3. **Test Auth Flow**:
   - Login via Google or email/password
   - Should redirect to `/dashboard` and stay there (no logout loop)
   - Refresh page → should remain authenticated

## Common Issues

### API URL Not Found

**Symptom**: `process.env.NEXT_PUBLIC_API_URL` is `undefined`

**Solution**:

1. Verify variable name starts with `NEXT_PUBLIC_`
2. Redeploy after setting the variable
3. Clear browser cache

### CORS Errors

**Symptom**: Browser console shows CORS errors

**Solution**:

1. Verify Render has `CORS_ORIGINS=https://your-vercel-app.vercel.app`
2. Ensure URLs match exactly (no trailing slashes)
3. Check that Render backend is running

### Cookie Not Sent to API

**Symptom**: Requests to API don't include cookies

**Solution**:

1. Verify `credentials: 'include'` in frontend code (already configured ✓)
2. Check cookie in DevTools → Application → Cookies
3. Verify cookie has `SameSite=None; Secure` flags
4. Ensure `NEXT_PUBLIC_API_URL` uses `https://`

### Login Loop

**Symptom**: Login succeeds, then immediately logs out

**Solution**:

1. This is typically a backend configuration issue
2. Check [Render Environment Variables](./render-env-vars.md#troubleshooting)
3. Verify Render has `WEB_APP_ORIGIN` set to your Vercel URL

## Build Configuration

Vercel auto-detects Next.js projects. Verify these settings in **Project Settings** → **Build & Development Settings**:

- **Framework Preset**: Next.js
- **Build Command**: `npm run build` (default)
- **Output Directory**: `.next` (default)
- **Install Command**: `npm install` (default)

## Performance Tips

### Enable Edge Runtime (Optional)

For faster cold starts, consider using Edge Runtime for API routes:

```typescript
// app/api/route.ts
export const runtime = 'edge';
```

### Configure Caching

In `next.config.js`:

```javascript
module.exports = {
  // Permanent redirects (301)
  async redirects() {
    return [
      {
        source: '/',
        destination: '/dashboard',
        permanent: false,
        has: [
          {
            type: 'cookie',
            key: 'consultaion_session',
          },
        ],
      },
    ];
  },
};
```

## See Also

- [Render Environment Variables](./render-env-vars.md)
- [Vercel Documentation](https://vercel.com/docs)
- [Next.js Environment Variables](https://nextjs.org/docs/app/building-your-application/configuring/environment-variables)
