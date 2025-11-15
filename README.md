# Consultaion
A platform that produces the best answer via multi-agent debate/voting.

## Quick Start
1. `cp .env.example .env` and set `DATABASE_URL`/LLM keys.
2. Backend: `cd apps/api && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
3. Run migrations: `alembic upgrade head`.
4. Frontend: `cd apps/web && npm install`.
5. `cd infra && docker compose up --build` (starts FastAPI, Next.js, Postgres).
6. Optional for local smoketests: set `FAST_DEBATE=1` to bypass the full LLM loop and return mock events instantly.

### Environment Flags

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Required Postgres connection string in production. |
| `JWT_SECRET` | Required unique signing secret; app now refuses to boot if unchanged. |
| `USE_MOCK` / `FAST_DEBATE` / `DISABLE_AUTORUN` | Control LiteLLM mocks, instant runs, and manual-start mode. |
| `DEFAULT_MAX_RUNS_PER_HOUR` / `DEFAULT_MAX_TOKENS_PER_DAY` | Per-user quotas. |
| `SENTRY_DSN` / `SENTRY_ENV` / `SENTRY_SAMPLE_RATE` | Optional backend error/trace reporting. |
| `NEXT_PUBLIC_SENTRY_DSN` | Optional web error capture (guards CDN script). |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_RECYCLE` | Postgres pooling (ignored on SQLite). |
| `ENABLE_METRICS` | Toggle `/metrics` counters for debates/SSE/exports. |
| `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_VOTE_THRESHOLD` | Client API origin & Aye threshold. |

### Production Checklist

- [ ] Set unique `JWT_SECRET`, `DATABASE_URL`, `SENTRY_DSN`, `NEXT_PUBLIC_SENTRY_DSN`.
- [ ] Serve behind HTTPS and update `CORS_ORIGINS`.
- [ ] Run `alembic upgrade head` before first deploy.
- [ ] Configure rate/usage limits (`RL_MAX_CALLS`, quotas) and monitor `/metrics`.
- [ ] Keep `FAST_DEBATE=0`, `USE_MOCK=0` for real LLMs.
- [ ] Enable Sentry + structured JSON logs for observability and ensure `/healthz` passes.
- [ ] Verify Nginx proxy buffering is disabled (SSE) and cookies forward correctly.

## Features
- Multi-agent debate pipeline with configurable agents/judges/budget per run.
- SSE runner UI plus `/runs` history, Hansard transcript, Voting Chamber, analytics, and downloadable reports.
- Email/password auth with JWT cookies, per-user `/runs` visibility, team sharing controls, and an admin console with audit logs.
- Alembic migrations, Postgres persistence, health/version endpoints, usage quotas, and structured rate limits.
- Pairwise vote tracking → Elo & Wilson confidence intervals powering a public leaderboard and Methodology brief.

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
