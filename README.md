# Consultaion
A platform that produces the best answer via multi-agent debate/voting.

## Quick Start
1. `cp .env.example .env` and set `DATABASE_URL`/LLM keys.
2. Backend: `cd apps/api && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
3. Run migrations: `alembic upgrade head`.
4. Frontend: `cd apps/web && npm install`.
5. `cd infra && docker compose up --build` (starts FastAPI, Next.js, Postgres).

## Features
- Multi-agent debate pipeline with configurable agents/judges/budget per run.
- SSE runner UI plus `/runs` history, detail pages, and downloadable reports.
- Alembic migrations, Postgres persistence, health/version endpoints, and rate limiting.

## Roadmap
- v0.1: SSE streaming, mock agents, mock judges, final synthesis ✅
- v0.2: LiteLLM real LLM calls, simple rubrics ✅
- v0.3: Postgres schema (debates, rounds, messages, scores), persistent logs ✅
- v0.4: Configurable depth for critique/revision rounds
- v0.5: Borda + Condorcet voting; Elo weighting
- v0.6: Safety/PII module, citation enforcement
