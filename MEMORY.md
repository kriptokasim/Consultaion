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

## Post-Patchset Readiness (2026-06-09)
- **Overall Score: ~8/10** — guard wired, search working, tests green
- Guard wiring: all 7 LLM routes protected
- Search: multi-field (id, prompt, mode, status) end-to-end
- Tests: 34 backend + 43 frontend, all passing
- Terms/Privacy: real content, P1 for lawyer review
- Remaining: API client consolidation, orchestrator refactor, E2E tests

## Premium Landing Page Overhaul (2026-06-10)
- **Overall Score: ~9/10** — strategic branding, scrollytelling workflow, and interactive Example Report Preview completed and verified.
- **Components Built**: Hero section (using Parliament.png), HowItWorks scrollytelling, ArenaAtAGlance, ExampleReportPreview, DifferentiationSection, UseCases.
- **Bypassed Testing Cache & JSON SQLite Serializer Issues**: Corrected endpoint test behavior for caching in test environments and SQLite's text-JSON representation checking.
- **Tests Coverage**: 356 pytest backend tests + 61 vitest frontend tests passing. Next.js production build completes successfully.

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

## Known Issues (as of 2026-06-09)
- LLM guard NOT wired into `POST /debates` and `POST /debates/{id}/start` (these already have granular rate limiting)
- API client consolidation needed (3 overlapping modules: apiClient.ts, api.ts, auth.ts)
- No E2E tests (Playwright)
- `orchestrator.py` (814 lines) — monolithic, needs refactoring
- Terms/Privacy are product-specific but not legal-grade (P1: lawyer review before paid launch)

## User Context
- Solo founder building Consultaion
- Preparing for pre-seed fundraising
- Working on model gateway, arena UX, and PLG optimizations
