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

## Report Specificity and Hardening (2026-06-10)
- **Overall Score: ~9.5/10** — generated decision reports hardened, semantic claim filter implemented, specificity rubric integrated, redundant verdict UI removed, and tests fully verified.
- **Backend Enhancements**:
  - Verification Status Hardening: Changed critic failures to set `unverified` and `verification_error = True` instead of faking 0.9 scores.
  - Claim Quality Filter: Added `claim_quality.py` to clean and filter markdown artifacts, boilerplate headers, and fragments shorter than 6 meaningful words.
  - Rubrics & Context-Awareness: Enforced specificity rubric (`specificity_score`, `genericity_risk`) and `context_needed` extraction to alert users when specific company stats are missing.
  - Model Position & Risk Polish: Shifted model position schemas from `strongest_point`/`concern` to `distinct_contribution`/`blind_spot` and enforced diagnostic-level risks.
- **Frontend & UI Enhancements**:
  - Updated `DecisionReportView` and `ModelPositionsTable` to match the new schema fields and display a warning card for missing context items.
  - Removed duplicate verdict blocks by hiding the raw markdown SynthesisCard whenever the structured report successfully renders.
- **Testing**: Added new tests to `test_synthesis_engine.py`, `test_report_builder.py`, `test_claim_quality.py`, and `DecisionReportView.test.tsx`. All tests are passing.


## Arena Pipeline Integrity & Fail-Closed Reporting (2026-06-10)
- **Goal**: Hardened the debate run pipeline UI hydration and enforced decision report integrity against LLM failures.
- **Key Enhancements**:
  - Implemented backend report validation (`report_integrity.py`) to detect malformed / incomplete JSON output and key injections.
  - Implemented fail-closed logic on backend (`synthesizer.py`) and frontend (`reportIntegrity.ts`, `ReportGenerationFailedCard.tsx`, and `DecisionReportView.tsx` render gate).
  - Fixed elapsed timer reset on hydration/refresh in `RunDetailClient.tsx` using `created_at` timestamp.
  - Updated polling to query React Query cache via `refetch()`.
  - Added dynamic stage progress metrics to the pipeline view.
  - Configured single-trigger timeline hydration on page refresh with fallback to `/debates/{id}/events`.
  - Upgraded response count parsing to correctly transition the active pipeline stage from `collecting_responses` to `scoring` as soon as all expected models respond.
- **Tests & Verification**: All pytest (65 tests) and vitest (96 tests) passed; Next.js builds successfully.

## UX, Search, Collapsible Sidebar & Marketing Storytelling Polish (2026-06-11)
- **Goal**: Unified global search, live metric states, landing page storytelling flow, and collapsible sidebar.
- **Key Enhancements**:
  - Hero Interaction: Refactored Arena button to scroll to input box and auto-focus, rather than launching default mock immediately.
  - Metrics Tutorial: Show onboarding instruction cards ("1. Ask", "2. Compare", "3. Decide") in metrics grid when no runs are active.
  - Empty/Failure States: Show informative screens on Leaderboard error/empty data and Participation page zero state. Added "Beta" badge to participation link in sidebar.
  - Storytelling Flow: Resolved scrollytelling container layout shifting and visual overlapping on desktop. Fixed sticky visual panel unpinning on final steps by using `overflow-x-clip` on the page wrapper container (to prevent browser vertical sticky unpinning rules), placing the sticky layout on the `<aside>` container, adding `pb-[40vh]` scroll room, and adjusting the scroll anchor triggers to `0.5`.
  - Debounced Search: Implemented live query search with 300ms debouncing, Esc closing, and outside click dismissal.
  - Back Button: Created reusable premium micro-animated BackButton component, integrated across dashboard and marketing views.
  - Collapsible Sidebar: Added persisted desktop sidebar collapse (w-20 vs w-72) toggling via hover-animated chevron button, storing preferences in `localStorage`.
- **Tests & Verification**: Integrated vitest coverage for BackButton component. All 110 tests passed and Next.js builds successfully. Pushed changes to the remote.

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

## SaaS Readiness & PLG Activation Polish (2026-06-12)
- **Goal**: Hardened SaaS readiness, added BYOK integrations, audit logs JSON/CSV streaming, data retention policies, dynamic team invites, pricing strategy, interactive PLG simulation, and completed visual sticky scrolling fixes.
- **Key Enhancements**:
  - **Visual Fixes**: Fixed final scrollytelling visual overlap on the HowItWorks step 4 with scroll bottom releasing and `overflow-x-hidden` on wrappers.
  - **PLG Activation**: Placed a "Try Demo" CTA in the hero directing to `/demo`, which simulates a multi-prompt deliberation flow with step-by-step model status cues and high-conversion post-simulation email capture.
  - **BYOK (Bring Your Own Key)**: Implemented `UserProviderKey` schemas, validation endpoints, and configuration dashboards under `/settings/provider-keys` with PostHog tracking.
  - **Audit & Compliance**: Built CSV/JSON streaming/export capabilities in `routes/audit_logs.py` and settings page at `/settings/audit-logs`. Added custom data-retention options (`/settings/data-retention`) and team role checklists (`/settings/team`).
  - **Enterprise Signal**: Integrated sales contact card in `/pricing`.
- **Tests & Verification**: Wrote new backend tests in `tests/test_saas_readiness.py` for BYOK and Audit Logs, which pass cleanly. Next.js production build verified success (Exit Code: 0).

## Staged Pipeline Resume Hardening (2026-06-13)
- **Goal**: Ensured pause/resume execution is correct, atomic, idempotent, quota-safe, and retry-safe.
- **Key Enhancements**:
  - **Stage Checkpoints**: Created `run_with_checkpoint` in `checkpoints.py` to cache stage outputs by hashing input data, preventing redundant execution.
  - **API Safety & Idempotency**: Hardened `/debates/{debate_id}/continue` to require explicit resume intent, perform conditional atomic database transitions (from `perspectives_ready` or `failed` to `scheduled`), validate cost/token limits, check provider circuit-breaker health, and enforce idempotency using `DebateContinuation` tracked by `X-Idempotency-Key` headers.
  - **Test Suite**: Wrote `test_stage_checkpoints.py` and `test_continue_api.py`. All tests passed cleanly.

## Agent Retry & Decision Brief Bug Fixes (2026-06-13)
- **Goal**: Resolved crash bugs in `/retry-agent` endpoint, fixed type mismatch in report view, and verified build.
- **Key Enhancements**:
  - **Backend Retry Bug Fixes**: Corrected `/debates/{debate_id}/retry-agent` to handle lack of `provider` in `AgentConfig` schema, corrected `increment_debate_usage` to pass `(session, user_id)` matching the service signature, and forced deep-copy on `final_meta` to trigger SQLAlchemy JSON column mutation tracking.
  - **Frontend Type & Import Fixes**: Resolved missing `React` import in `PipelineProgress.tsx` and resolved static TypeScript type error on `quality_meta.scores` in `DecisionReportView.tsx` by casting.
- **Tests & Verification**: Verified all backend tests pass successfully (11/11 in `test_debates_api.py`) and Next.js production build compiles successfully (Exit Code: 0).

## Staged Checkpoints & Retry Safety Hardening (2026-06-14)
- **Goal**: Hardened the debate and arena pipeline execution stages with granular checkpoints, retry-safe worker tasks, and cascade stage-local retries.
- **Key Enhancements**:
  - **Granular Synthesizer & Divergence Checkpoints**: Split report generation into `"synthesis_draft"` (scoring, claim extraction, drafting) and `"verification"` (quality critique, self-healing loop). Wrapped divergence computation under `"divergence_analysis"`. Both serialize state to database checkpoint records.
  - **Downstream Cascade Retry Clearing**: Updated `/api/v1/debates/{debate_id}/retry` to clear specific downstream stage checkpoints and corresponding database entities (scores, votes, messages, divergence reports) based on the target retry stage.
  - **Tests**: Created comprehensive tests covering attempt tracking, serialization, and correct cascade clearing. All tests pass cleanly.

## Continuation Lifecycle, Refresh-Safe Idempotency & Schema Contract Verification (2026-06-15)
- **Goal**: Standardized runtime SSE continuation tracking, centralized database continuation state transitions, made frontend continuation state refresh-safe, and implemented schema contract checks.
- **Key Enhancements**:
  - **Continuation DB Lifecycle Updates**: Integrated centralized state updates inside `orchestrator.py` via `apps/api/services/continuations.py` to correctly map continuation record status to `running`, `completed`, or `failed` as debate execution proceeds.
  - **Refresh-Safe continuation state**: Refactored `apps/web/hooks/useRunWorkspace.ts` to sync the active idempotency key in `sessionStorage` and restore `isContinuing` state directly from the hook across page refreshes.
  - **Schema Contract E2E Tests**: Added comprehensive database table existence checks inside `tests/test_schema_contract.py`.
- **Tests & Verification**: Verified that all new automated test suites (`test_schema_contract.py`, `test_continue_api.py`, `test_continuations_service.py`) pass 100% successfully.




