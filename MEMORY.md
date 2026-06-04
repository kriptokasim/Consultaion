# MEMORY.md - Long-Term Memory

## About This Repo
Consultaion is a multi-agent AI debate platform — users submit one prompt and get synthesized answers from multiple LLMs (GPT-4o, Claude, Gemini, DeepSeek). The product name is intentionally spelled "Consultaion" (not Consultation).

## Tech Stack
- **Backend:** Python 3.11, FastAPI, SQLModel/SQLAlchemy, Alembic, Celery, Redis
- **Frontend:** Next.js 15, React 19, Tailwind CSS, Zustand, TanStack React Query
- **Infra:** Docker Compose, Nginx, Supabase (Postgres), Render + Vercel deployment
- **Monitoring:** Sentry, PostHog, Langfuse
- **Testing:** pytest (backend), Playwright E2E (frontend)

## VC-Readiness Assessment (2026-06-04)
- **Overall Score: 6.5/10** — strong product/code, weak on tests/legal
- **Strengths:** Product positioning (9/10), Documentation (9/10), CI/CD (8/10)
- **Critical Gaps:** Test coverage 30% (need 60%+), no LICENSE, no ToS, no CI security scanning
- **Full report:** ~/Desktop/consultaion-vc-readiness.md
- **Action items:** P0 = LICENSE, ToS, test coverage, clean .db files

## Key Files to Know
- `apps/api/main.py` — FastAPI app entry (419 lines)
- `apps/api/orchestrator.py` — debate execution (814 lines, god file)
- `apps/api/agents.py` — LLM agent roles (829 lines)
- `apps/api/config.py` — Pydantic settings (493 lines)
- `apps/api/models.py` — 16 SQLModel tables
- `docs/investor-positioning.md` — pitch narrative
- `docs/vc-readiness-scorecard.md` — existing VC checklist
- `docs/pricing-strategy.md` — 3-tier pricing
- `docs/defensibility.md` — moat strategy

## Known Issues (as of 2026-06-04)
- `orchestrator.py` mixes sync/async database access
- `votes_router` registered twice in main.py
- 8 stale .db files previously tracked in git
- Frontend has zero unit tests
- No API versioning (/api/v1/)
- `core/settings.py` and `config.py` coexist (potential confusion)

## User Context
- Solo founder building Consultaion
- Preparing for pre-seed fundraising
- Working on model gateway, arena UX, and PLG optimizations
