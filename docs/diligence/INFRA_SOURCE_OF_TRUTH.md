# Infrastructure Source of Truth

This document defines the production hosting, database, domains, and configuration management architecture for Consultaion.

---

## Hosting Providers & Configuration Paths

### Backend API: Render
- **Hosting Service:** Web Service on Render (Docker-based runtime).
- **Configuration Path:** Dockerfile located at `apps/api/Dockerfile`.
- **Custom Domains:** `api.consultaion.com`
- **SSL:** Render handles SSL certificate generation and auto-renewal (Let's Encrypt) at the load balancer level. SSL/TLS is enforced; all HTTP traffic is redirected to HTTPS.

### Frontend Web App: Vercel
- **Hosting Service:** Next.js Serverless on Vercel.
- **Configuration Path:** Next.js settings in `apps/web/next.config.mjs` and deployment settings in Vercel dashboard.
- **Custom Domains:** `consultaion.com` (root domain) and `www.consultaion.com`.
- **SSL:** Vercel handles SSL/TLS termination automatically at their edge network.

---

## Database Hosting & Connection Patterns

- **Provider:** Managed PostgreSQL database on Supabase (running standard Postgres 16).
  > [!NOTE]
  > The local `supabase/` configuration folder has been removed from this repository to clean up legacy files and establish a single source of truth. All schema updates are managed exclusively via Alembic migrations under `apps/api/alembic/`.
- **Connection Mode:** Session pool connection strings mapped to Render API instances.
- **SSL Requirement:** Database connections are strictly configured to require SSL (e.g. `sslmode=require`).

---

## Environment Variables Configuration

Sensitive credentials and configuration flags are injected at runtime by the respective platforms.

### Backend Environment Variables (Render Dashboard)
- `DATABASE_URL`: Connection string to Supabase PostgreSQL database.
- `JWT_SECRET`: HS256 JWT encryption key.
- `STRIPE_API_KEY` / `STRIPE_WEBHOOK_SECRET`: Stripe payment processing credentials.
- `LITELLM_API_KEY`: API keys for Anthropic, OpenAI, Gemini, etc. managed via LiteLLM routing.

### Frontend Environment Variables (Vercel Dashboard)
- `NEXT_PUBLIC_API_URL`: Set to `https://api.consultaion.com`.
- `NEXT_PUBLIC_APP_URL`: Set to `https://consultaion.com`.
