# Consultaion
A platform that produces the best answer via multi-agent debate/voting.

## Quick Start
1. `cp .env.example .env` and set `DATABASE_URL`/LLM keys.
2. Backend: `cd apps/api && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
3. Run migrations: `alembic upgrade head`.
4. Frontend: `cd apps/web && npm install`.
5. `cd infra && docker compose up --build` (starts FastAPI, Next.js, Postgres).
6. Optional for local smoketests: set `FAST_DEBATE=1` to bypass the full LLM loop and return mock events instantly.

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
- When a limit is hit the UI surfaces a dismissible banner with the reset time, and audit logs capture the violation.

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
