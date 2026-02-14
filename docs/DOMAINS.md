# Domain & URL Configuration

## Production Domains

| Service   | Domain                          | Purpose                  |
| --------- | ------------------------------- | ------------------------ |
| Web (app) | `web.consultaion.com`           | Next.js frontend         |
| API       | `api.consultaion.com`           | FastAPI backend          |

## Required Environment Variables

### Frontend (Vercel / Next.js)

| Variable              | Example                              | Description                    |
| --------------------- | ------------------------------------ | ------------------------------ |
| `NEXT_PUBLIC_APP_URL` | `https://web.consultaion.com`        | Canonical app origin (OG/SEO)  |
| `NEXT_PUBLIC_API_URL` | `https://api.consultaion.com`        | Backend API origin             |

### Backend (Render / FastAPI)

| Variable          | Example                          | Description                         |
| ----------------- | -------------------------------- | ----------------------------------- |
| `WEB_APP_ORIGIN`  | `https://web.consultaion.com`    | Allowed origin for CORS & cookies   |
| `CORS_ORIGINS`    | `https://web.consultaion.com`    | Comma-separated allowed origins     |
| `PUBLIC_API_BASE` | `https://api.consultaion.com`    | Base URL for absolute links in API responses |

## Local Development

```bash
# .env.local (frontend)
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000

# .env (backend)
WEB_APP_ORIGIN=http://localhost:3000
CORS_ORIGINS=http://localhost:3000
```

## Architecture

All URL construction in the frontend flows through a single runtime config module:

```
apps/web/lib/config/runtime.ts
```

Exports:

- `APP_ORIGIN` — canonical web origin
- `API_ORIGIN` — API origin (uses `/api` proxy in prod browser, direct URL in SSR/dev)
- `apiUrl(path)` — builds full API URL
- `absoluteUrl(path)` — builds full app URL

**Rule:** No file other than `runtime.ts` should read `NEXT_PUBLIC_API_URL` or `NEXT_PUBLIC_APP_URL` directly.

## CI Guardrails

The `lint:urls` script (`scripts/check_no_hardcoded_urls.ts`) prevents regressions by scanning for:

- `onrender.com`
- `vercel.app`
- `localhost:`

Allowlisted paths: `README*`, `docs/**`, `.env.example`, `**/*.md`
