# Quick Deployment Checklist – Patchset 51.0

## ⚡ TL;DR - What to Do Right Now

### 1. Render (Backend API)

In Render Dashboard → Your API Service → Environment Variables, set:

```bash
ENV=production
WEB_APP_ORIGIN=https://consultaion.vercel.app
CORS_ORIGINS=https://consultaion.vercel.app
JWT_SECRET=<run: openssl rand -base64 32>
```

**Critical**: Replace `consultaion.vercel.app` with YOUR actual Vercel URL.

### 2. Vercel (Frontend)

In Vercel Dashboard → Project Settings → Environment Variables, set:

```bash
NEXT_PUBLIC_API_URL=https://consultaion.onrender.com
```

**Critical**: Replace `consultaion.onrender.com` with YOUR actual Render URL.

### 3. Deploy Both

- **Render**: Will auto-deploy on git push
- **Vercel**: Click "Redeploy" in dashboard (required for env vars to take effect)

### 4. Test

Go to `https://your-app.vercel.app`:

- ✅ Login with Google → Should stay on /dashboard (no redirect loop)
- ✅ Refresh page → Should stay logged in
- ✅ /me endpoint → Should return user data (not 401)

---

## 🔍 How to Verify It's Working

### Open Browser DevTools

**Application Tab** → Cookies → `consultaion.onrender.com`:

- Name: `consultaion_session`
- Secure: ✓
- SameSite: None
- HttpOnly: ✓

**Network Tab** → Filter for `/me`:

- Request shows `Cookie: consultaion_session=...`
- Response is `200 OK` with user data
- Response headers include `Access-Control-Allow-Credentials: true`

---

## 🚨 Troubleshooting

### Still Getting Login Loop?

**Check Render env vars**:

```bash
WEB_APP_ORIGIN=https://consultaion.vercel.app  # Must match exactly
CORS_ORIGINS=https://consultaion.vercel.app    # Must match exactly
ENV=production                                 # Must be set
```

**Check cookie in browser**:

- If `SameSite=Lax` → Render didn't detect production mode
- If no cookie at all → Check Network tab for Set-Cookie header

**Check CORS**:

- Open Network tab
- Look at API response headers
- Should see `Access-Control-Allow-Origin: https://your-vercel-app.vercel.app`

---

## 📚 Full Documentation

- [Complete Render Guide](./deployment/render-env-vars.md)
- [Complete Vercel Guide](./deployment/vercel-env-vars.md)
- [Full Walkthrough](../.gemini/antigravity/brain/6583b242-0118-433f-892d-f33b16e2e87f/walkthrough.md)

---

## 💡 Why This Works

The code already supports cross-origin auth (implemented in a previous commit).

The fix is **configuration**, not code:

1. Render auto-detects production via `RENDER` env var (set by platform)
2. In production, cookies use `SameSite=None; Secure` (required for cross-site)
3. CORS allows your Vercel URL with credentials
4. Frontend sends `credentials: 'include'` on all API calls

**Nothing to code** - just set the env vars and deploy!
