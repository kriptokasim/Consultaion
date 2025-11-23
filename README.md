# Consultaion
A platform that produces the best answer via multi-agent debate/voting.

> **Brand note:** The spelling “Consultaion” is intentional – it’s the product name for this multi-agent AI parliament, not a typo. Keep it consistent across docs, UI, and deploys.

## Quick Start
1. `cp .env.example .env` and set `DATABASE_URL`/LLM keys.
2. Backend: `cd apps/api && python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
3. Run migrations: `alembic upgrade head`.
4. Frontend: `cd apps/web && npm install`.
5. `cd infra && docker compose up --build` (starts FastAPI, Next.js, Postgres).
6. Optional for local smoketests: set `FAST_DEBATE=1` to bypass the full LLM loop and return mock events instantly.

📚 Need endpoint details or diagrams? See `docs/API.md` and `docs/ARCHITECTURE.md`. Progress against the audit plan lives in `IMPROVEMENT_PLAN.md` / `IMPROVEMENTS_SUMMARY.md`.

> **Python runtime:** The FastAPI backend and its pytest suite currently target **Python 3.11.x**. Running under newer interpreters (3.12/3.13) causes ASGI/TestClient hangs on POST requests, so stick to 3.11 for local dev, CI, and Docker builds until upstream fixes land.

### Environment Flags

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Required Postgres connection string in production. |
| `JWT_SECRET` | Required unique signing secret; app now refuses to boot if unchanged. |
| `LOG_LEVEL` | Controls backend JSON log verbosity (`INFO`, `DEBUG`, etc.). |
| `USE_MOCK` / `FAST_DEBATE` / `DISABLE_AUTORUN` | Control LiteLLM mocks, instant runs, and manual-start mode. |
| `DEFAULT_MAX_RUNS_PER_HOUR` / `DEFAULT_MAX_TOKENS_PER_DAY` | Per-user quotas. |
| `SENTRY_DSN` / `SENTRY_ENV` / `SENTRY_SAMPLE_RATE` | Optional backend error/trace reporting. |
| `NEXT_PUBLIC_SENTRY_DSN` | Optional web error capture (guards CDN script). |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_RECYCLE` | Postgres pooling (ignored on SQLite). |
| `ENABLE_METRICS` | Toggle `/metrics` counters for debates/SSE/exports. |
| `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_VOTE_THRESHOLD` | Client API origin & Aye threshold. |
| `WEB_APP_ORIGIN` | Frontend base used for OAuth redirects (default `http://localhost:3000`). |
| `BILLING_PROVIDER` / `STRIPE_*` / `BILLING_CHECKOUT_*` | Billing provider selection, Stripe keys, and checkout redirect URLs. |
| `N8N_WEBHOOK_URL` | Optional automation webhook target for subscription/usage events. |
| `WEB_APP_ORIGIN` | Frontend base used for OAuth redirects (default `http://localhost:3000`). |

### Model catalog & providers
- Consultaion uses LiteLLM as an internal gateway and supports OpenRouter, OpenAI, Anthropic, and Gemini (server-side keys only; users do not supply their own).
- Configure provider API keys in `.env` (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`); models auto-enable when keys are present.
- A curated catalog is exposed via `GET /models`; the recommended model is set in the registry (`ModelConfig.recommended`) and used as the default when creating debates.


### Production Checklist

- [ ] Set unique `JWT_SECRET`, `DATABASE_URL`, `SENTRY_DSN`, `NEXT_PUBLIC_SENTRY_DSN`; avoid default DB creds.
- [ ] Serve behind HTTPS and update `CORS_ORIGINS`; keep `ENABLE_CSRF=1`.
- [ ] Run `alembic upgrade head` before first deploy.
- [ ] Configure rate/usage limits (`RL_MAX_CALLS`, quotas) and use Redis-backed IP rate limiting in prod (`RATE_LIMIT_BACKEND=redis`, `REDIS_URL` set); monitor `/metrics`.
- [ ] Keep `FAST_DEBATE=0`, `USE_MOCK=0`, and set `REQUIRE_REAL_LLM=1` when using real LLMs.
- [ ] Enable Sentry + structured JSON logs for observability and ensure `/healthz` passes.
- [ ] Verify Nginx proxy buffering is disabled (SSE) and cookies forward correctly.

## Features
- Multi-agent debate pipeline with configurable agents/judges/budget per run.
- SSE runner UI plus `/runs` history, Hansard transcript, Voting Chamber, analytics, and downloadable reports.
- Email/password auth with JWT cookies, per-user `/runs` visibility, team sharing controls, and an admin console with audit logs.
- Alembic migrations, Postgres persistence, health/version endpoints, usage quotas, and structured rate limits.
- Pairwise vote tracking → Elo & Wilson confidence intervals powering a public leaderboard and Methodology brief.
- Web UI uses an “Amber-Mocha” cockpit theme (warm cream background with amber accents) across landing, dashboard, and live views.

### Test coverage
- `pytest -q` in `apps/api` now includes the audit-derived suites for orchestrator helpers, ratings, rate limits, SSE channel hygiene, and the multi-LLM registry (`apps/api/tests/test_*.py`). Run them locally after migrations to catch regressions early.

### API Router Layout
- `apps/api/routes/auth.py`: login/register/session endpoints.
- `apps/api/routes/stats.py`: health/ready/metrics plus model/hall-of-fame stats.
- `apps/api/routes/debates.py`: debate/run lifecycle, exports, and streams.
- `apps/api/routes/teams.py`: team creation and membership/sharing.
- `apps/api/routes/admin.py`: admin-only listings and rating maintenance.

### Teams & Sharing
- Create teams, invite collaborators, and assign debates to a team via the `/runs` “Share” control.
- User-scoped `/runs` filters (Mine / Team / All for admins) ensure the archive stays organized.

### Rate Limits & Quotas
- API enforces IP-based burst limits plus per-user hourly run counts and daily token quotas (`DEFAULT_MAX_RUNS_PER_HOUR`, `DEFAULT_MAX_TOKENS_PER_DAY`).
- When a limit is hit the UI surfaces a dismissible banner with the reset ETA countdown, and audit logs capture the violation.

### Audit Log
- Every critical action (register, login, share run, exports, rate-limit block) lands in `audit_log`.
- Admins can review the latest entries under `/admin` → “Audit log” tab.

### Voting Mapping
- Judge score events stream into the Voting Chamber; scores above `NEXT_PUBLIC_VOTE_THRESHOLD` march through the Aye lobby.
- Run detail pages now show Hansard, Scoreboard, Voting Chamber, Voting Section, and raw timeline using the new Sepia/Amber palette.

## Roadmap
- v0.1: SSE streaming, mock agents, mock judges, final synthesis ✅
- v0.2: LiteLLM real LLM calls, simple rubrics ✅
- v0.3: Postgres schema (debates, rounds, messages, scores), persistent logs ✅
- v0.4: Configurable depth for critique/revision rounds
- v0.5: Borda + Condorcet voting; Elo weighting
- v0.6: Safety/PII module, citation enforcement
