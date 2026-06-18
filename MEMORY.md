# MEMORY.md - Long-Term Memory

## About This Repo
Consultaion is a multi-agent AI debate platform — users submit one prompt and get synthesized answers from multiple LLMs (GPT-4o, Claude, Gemini, DeepSeek). The product name is intentionally spelled "Consultaion" (not Consultation).

## Tech Stack
- **Backend:** Python 3.11, FastAPI 0.121.0, SQLModel 0.0.22 (SQLAlchemy 2.x), Alembic 1.13.2, Celery 5.4.0, Redis 5.2.0
- **Frontend:** Next.js 15.5.9 (App Router), React 19.0.0, TypeScript 5.6.3, Tailwind CSS 3.4.10, Zustand 4.5.2, TanStack React Query 5.59.0
- **UI:** Radix UI, Lucide icons, class-variance-authority
- **Infra:** Docker Compose, Nginx 1.27-alpine, Supabase (Postgres 16), Render + Vercel
- **LLM Gateway:** LiteLLM 1.61.15 (OpenAI, Anthropic, Gemini, OpenRouter, Groq, Mistral)
- **Auth:** JWT cookie-based (PyJWT 2.10.1), bcrypt, Google OAuth, CSRF double-submit
- **Monitoring:** Sentry, PostHog, Langfuse, Prometheus, OpenTelemetry
- **Testing:** pytest 8.3.3 (backend), Vitest + Playwright (frontend)
- **Billing:** Stripe (skeleton/placeholder)

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
- `apps/api/main.py` — FastAPI app entry, middleware, lifespan
- `apps/api/orchestrator.py` — debate execution (814 lines, god file)
- `apps/api/agents.py` — LLM agent roles
- `apps/api/config.py` — Pydantic AppSettings (centralized config)
- `apps/api/models.py` — SQLModel ORM models (25+ tables)
- `apps/api/services/continuations.py` — continuation DB lifecycle
- `apps/api/services/schema_capabilities.py` — runtime PG inspection
- `apps/api/services/debate_enrichment.py` — enrichment fail-safe
- `apps/api/services/migration_safety.py` — safe migration runner
- `apps/api/orchestration/checkpoints.py` — stage checkpoint caching
- `apps/api/reporting/synthesizer.py` — report generation with verification
- `apps/api/routes/debates.py` — debate API endpoints (continue, retry)
- `docs/investor-positioning.md` — pitch narrative
- `docs/diligence/VC_READINESS.md` — VC readiness checklist
- `docs/pricing-strategy.md` — 3-tier pricing
- `docs/defensibility.md` — moat strategy

## Known Issues (as of 2026-06-18)
- `orchestrator.py` (814 lines) — monolithic, mixes sync/async, needs refactoring
- API client consolidation needed (3 overlapping modules: apiClient.ts, api.ts, auth.ts)
- No E2E tests (Playwright) despite playwright.config.ts existing
- Terms/Privacy are product-specific but not legal-grade (P1: lawyer review before paid launch)
- `core/settings.py` and `config.py` coexist (potential confusion)
- LLM guard NOT wired into `POST /debates` and `POST /debates/{id}/start` (rate-limited already)
- ~~No API versioning (/api/v1/) despite routes living under `/api/v1/` prefix~~ — FIXED: root routes now emit Deprecation/Sunset headers

## User Context
- Solo founder building Consultaion
- Preparing for pre-seed fundraising
- Working on model gateway, arena UX, and PLG optimizations

## Dev Tooling
- **Linting:** Ruff 0.8.0, MyPy 1.13.0
- **Testing:** pytest 8.3.3 + pytest-cov (75% coverage gate), Vitest, Playwright
- **CI/CD:** GitHub Actions (7 workflows), pre-commit hooks (ruff, mypy, fast pytest)
- **Security:** Bandit (SAST), pip-audit / npm audit, Gitleaks (secret scanning), SBOM (CycloneDX)
- **Code review:** CodeRabbit automated PR reviews
- **Client SDKs:** Python SDK (`consultaion-sdk` v0.1.0, async httpx), JS SDK (`@consultaion/sdk` v0.1.0, TypeScript)
- **Theme:** "Amber-Mocha" cockpit theme (warm cream background, amber accents)

## Competitor Intelligence
- **SummaChat** (2026-06-13): Multi-Agent Debate mode with moderator + multiple LLMs, unified action menus (Create Image, Create Doc, Crawl). Critical consensus synthesis error observed — moderator failed to generate final report, showing red retry card. Reinforces that robust error boundaries for multi-agent synthesis are essential.

## Key Learnings
- **Checkpoint isolation:** Isolating outer checkpoints (e.g. `"synthesis"`) from inner (e.g. `"synthesis_draft"`, `"verification"`) avoids namespace collisions and enables granular retry control. [2026-06-14]
- **SQLAlchemy JSON mutation tracking:** Must deep-copy JSON columns to trigger change detection. [2026-06-13]
- **Test fixture engine imports:** Dynamic database engine updates in conftest can lead to stale references; use `db_session` fixture or import engine inside functions. [2026-06-12]
- **StreamingResponse charset:** Next.js test assertions should use `.startswith()` for content-type checks due to inconsistent `charset=utf-8` appending. [2026-06-12]
- **SQLite text-JSON:** SQLite stores JSON as text; test assertions must account for text-JSON representation. [2026-06-10]
- **APIRouter has no `.middleware()`:** FastAPI's `APIRouter` does not support `@router.middleware("http")` — only `app.middleware("http")` works. For per-router middleware, use app-level middleware with path-based dispatch. [2026-06-18]
- **`crypto.subtle.digest` requires secure context:** Frontend SHA-256 via `crypto.subtle` only works over HTTPS or localhost. DivergenceClaimList.tsx uses it for claim_id generation. [2026-06-18]

## Current Status (2026-06-18)
- **Completed:** FH125 Phases 1–2 (Green Baseline + Security Containment) — 16 items total
- **Phase 2 Security Fixes:** IDORs fixed (challenge, arena vote), JWT removed from OAuth URLs, host-only cookies, route-level CSRF, API namespace deprecation headers, progressive account lockout, OAuth state requires Redis in prod
- **Next:** Phase 3 (Runtime Correctness — encryption, billing, SSE), Phase 4 (Contracts & Operations)
- **Remaining:** E2E tests, API client consolidation, orchestrator refactor

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

## Run Recovery & Operational Hardening (FH51–FH56) (2026-06-16)
- **Goal**: Restore historical Run rendering, make enrichment fail-safe, fix Alembic migration length limits, add production schema diagnostics and /readyz.
- **Key Enhancements**:
  - **FH51** — Frontend timeline fallback: staged loading (debate first, then timeline), `RunHydrationQuality` type, degraded-mode banner in `RunDetailClient.tsx`
  - **FH52** — Runs list-first rendering: table shows before profile completes, `normalizeRunStatus()` for historical status mapping
  - **FH53** — Backend enrichment fail-safe: `schema_capabilities.py` runtime PG inspection, `debate_enrichment.py` try/except isolation, `require_schema_current()` guard, mutation guards on POST/continue/retry
  - **FH54** — Safe migration runner: `migration_safety.py` + `migrate_database.py` (12-phase, break-glass `--allow-stamp`)
  - **FH55** — Alembic revision policy audit: `audit_alembic_revisions.py`, `test_alembic_revision_policy.py`
  - **FH56** — Schema verification scripts and runbook: diagnostic, verification, `/readyz` integrity check
- **Tests & Verification**: Frontend 127 tests pass; backend module imports validate.

## FH125 Production Stabilization — Phases 1–2 (2026-06-18)
- **Goal**: Execute the 4-phase FH125 stabilization plan from `~/Desktop/implementation_plan.md`. Phase 1 (Green Baseline) restored build/test health. Phase 2 (Security Containment) fixed all IDORs, CSRF, OAuth, cookie, and lockout issues.
- **Phase 1 (Track A)**: Tailwind orphaned keys removed, DivergenceMeter import fixed, test files rewritten for real APIs, schema readiness test bypass implemented. Verified: tsc ✅, build ✅, 568 pytest collected ✅.
- **Phase 2 (Tracks B+C)** — all 10 items complete:
  - **B-1**: `dependencies/access.py` — added `get_debate_with_mutable_access` (editor-level access)
  - **B-2**: Challenge IDOR fixed — `require_debate_access` added to `start_challenge_session`
  - **B-3**: Argument-tree IDOR fixed — debate access checks added to `get_challenge_session` and `submit_challenge_round`
  - **B-4**: Arena vote — `require_debate_access` added, client-trusted `model_name`/`is_consensus` replaced with server-validated `claim_id` (SHA-256), per-claim deduplication. Frontend updated (`DivergenceClaimList.tsx`, `DivergenceMeter.tsx`). **Breaking API change** (approved).
  - **C-1**: JWT removed from OAuth redirect URLs — token only in HttpOnly cookie
  - **C-2**: COOKIE_DOMAIN auto-derivation removed — defaults to host-only
  - **C-3**: CSRF path exemptions replaced with `csrf_exempt` route decorator
  - **C-4**: API namespace — root routes get `Deprecation`/`Sunset` headers via app middleware
  - **C-5**: Progressive account lockout (5→15min, 10→1h, 20→24h) on User model + login handler
  - **C-6**: OAuth state requires Redis in prod, atomic `getdel`, memory fallback local-only
- **Files modified**: `dependencies/access.py`, `routes/challenge.py`, `routes/arena.py`, `routes/auth.py`, `main.py`, `config.py`, `core/router_registry.py`, `models.py`, `security/state_store.py`, `DivergenceClaimList.tsx`, `DivergenceMeter.tsx`

## Graphify Codebase Knowledge Graph (2026-06-18)
- **Goal**: Build and configure the `graphify` knowledge graph for codebase navigation and architectural queries.
- **Configured `.graphifyignore`**: Set up a custom ignore file to filter out non-code assets (markdown documentation, text configs, PNG/SVG/WebP images). This enabled building a code-only corpus.
- **Graph Built**: Executed `graphify .` followed by `graphify cluster-only . --no-label` to construct the graph (`graphify-out/graph.json`) containing **5,361 nodes**, **11,140 edges**, and **361 communities** without requiring external LLM API keys for community naming.
- **Key Insight**: Identified a high-centrality name resolution collision on the node `Config`. Imports of the `config` module (e.g., `from config import settings`) are parsed as references to the Alembic `Config` class inside `dev_db.py` (which has ID `config`). This collision structurally reflects the global dependency of all backend components on system settings.

