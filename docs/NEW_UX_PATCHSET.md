# Consultaion New UX — Master Patchset Plan

Date: 2026-09-20
Source: uploaded Consultaion handoff (screens + change-list + component inventory)
Target repo: `kriptokasim/Consultaion`

## Branch map

- `main`: current production baseline. DO NOT modify directly.
- `feat/consultaion-new-ux`: our integration branch, currently 6 commits ahead of `main`. Contains the first New UX foundation/scaffold and is the branch I will own.
- `agent/new-ux-ui-foundation`: agent branch, created from `feat/consultaion-new-ux`. The other coding agent should implement the mechanical/frontend consolidation here.
- Suggested future merge direction:
  `agent/new-ux-ui-foundation` -> reviewed -> `feat/consultaion-new-ux` -> verification -> optional dedicated repo/fork -> deployment.

## Working principle

The handoff is a UX/architecture simplification, not a reason to rewrite the backend.

Keep:
- FastAPI API contracts
- PostgreSQL / Alembic
- Celery / Redis
- auth and OAuth
- billing and spend controls
- model gateway / OpenRouter / provider adapters
- SSE transport
- continuation/recovery state machine
- existing synthesis and verification backend

Replace/consolidate primarily:
- duplicated workspace renderers
- duplicated report shells
- duplicated navigation
- duplicated model pickers
- onboarding furniture
- inconsistent loading/error/empty UI
- marketing page structure

Do NOT delete old renderers merely because the new workspace exists. Delete only after the unified adapter covers their behavior and tests.

---

# Patchset 00 — New UX foundation [DONE / ours]

Branch: `feat/consultaion-new-ux`

Already added:
- `apps/web/styles/tokens.css`
- `apps/web/styles/new-ux.css`
- `apps/web/lib/modes.ts`
- `apps/web/components/run/RunWorkspaceNew.tsx`
- `apps/web/app/new/page.tsx`
- `docs/new-ux-migration.md`
- layout import for new UX CSS

Purpose:
- prove the handoff can sit on top of the current run API
- keep main untouched
- establish the visual/token layer and first unified workspace route

Important:
This is scaffolding, not final production UI. The current prototype intentionally does not yet replace the existing `/live`, report, dashboard or marketing routes.

---

# Patchset 01 — Semantic design system + visual migration [AGENT]

Reference:
- `handoff/tokens.css`
- `screens/Consultaion App Shell.dc.html`
- `screens/Consultaion Homepage.dc.html`

Files:
- `apps/web/styles/tokens.css`
- `apps/web/styles/new-ux.css`
- `apps/web/tailwind.config.ts`
- `apps/web/eslint.config.*` / equivalent ESLint config
- `apps/web/styles/globals.css`

Tasks:
1. Make the handoff semantic tokens canonical:
   `surface, surface-raised, ink, ink-soft, ink-faint, rule, rule-strong, spot, spot-text, alarm, alarm-text, on-spot`.
2. Add Source Serif 4 400/600/italic 400.
3. Remove component-level raw Tailwind palette usage from migrated components.
4. Add the restricted-syntax lint guard from the handoff.
5. Introduce `data-surface="ink"` for app surfaces and paper surface for marketing/report.
6. Preserve accessibility contrast rather than mechanically copying every handoff color.
7. Eliminate the old gradient/orb/text-shadow treatment where the new screen replaces it.

Acceptance:
- lint catches new raw palette classes in migrated components
- typography matches the handoff
- marketing/report remain paper
- app shell/workspace uses ink
- no global regression for existing shadcn components

Do not:
- modify API
- change billing
- delete old components yet

---

# Patchset 02 — Unified Run Workspace + state split [OURS]

Reference:
- `screens/Consultaion Run Workspace.dc.html`
- `apps/web/hooks/useRunWorkspace.ts`

This is the highest-risk frontend patchset and stays with me.

Goal:
Turn the current mode-specific UI into one canonical Run Workspace while preserving all runtime semantics.

Target architecture:

`RunWorkspace`
- composer state
- stream state
- report state
- mode descriptor
- panel picker
- shared status/recovery

Split:
- `useComposer`
- `useRunStream`
- `useRunReport`

without changing wire contracts.

Mode descriptor:
```ts
type Mode = {
  id: 'arena' | 'debate' | 'compare' | 'oracle' | 'redteam'
  name: string
  blurb: string
  panelSize: [number, number]
  crossTalk: boolean
  rounds: number
  synthesis: boolean
}
```

Critical behavioral requirements:
- Arena: independent model responses + synthesis
- Compare: no synthesized verdict
- Debate: cross-talk/round semantics retained
- Oracle: exactly one model
- RedTeam: adversarial semantics retained
- SSE remains exclusively owned by the workspace stream layer
- continuation/retry/outcomeUnknown remain intact
- polling fallback remains intact
- partial responses render
- no ghost/empty model cards
- model status derives from real events, not guessed timers

Do not remove the old renderers until this patchset's compatibility tests pass.

Acceptance:
- current existing run URLs still open
- live Arena streams correctly
- Compare never fabricates a verdict
- Debate/Parliament behavior is not silently flattened
- reload/reconnect preserves run state
- continuation retry remains idempotent

---

# Patchset 03 — Canonical panel picker + shell state family [AGENT]

Reference:
- `screens/Consultaion First Run.dc.html`
- `screens/Consultaion Run Workspace.dc.html`
- component inventory

Create:
- `apps/web/components/ui/PanelPicker.tsx`
- `apps/web/components/ui/StatusPill.tsx`
- `apps/web/components/ui/ListSkeleton.tsx`
- `apps/web/components/ui/EmptyState.tsx`
- `apps/web/components/errors/ErrorBanner.tsx` (or migrate existing one)

PanelPicker:
- one data model
- inline presentation for composer
- sheet presentation for mid-run
- minimum-two-model rule except Oracle
- reuse current model catalog/selection data
- accessible keyboard/touch interaction

Status vocabulary:
- Live
- Closed
- Needs you
- Failed

State family:
- no decorative cards
- skeletons follow actual list rhythm
- errors state what was tried + reference + retry
- offline bar says the run continues server-side

Also fix mobile drawer:
- `role="dialog"`
- `aria-modal="true"`
- focus trap
- distinct z-indexes for backdrop/drawer/navigation

Acceptance:
- no duplicate model-picker logic in migrated surfaces
- no drawer accessibility violations
- all state components have unit tests

---

# Patchset 04 — App Shell + navigation consolidation [AGENT]

Reference:
- `screens/Consultaion App Shell.dc.html`

Create:
- `apps/web/lib/nav.ts`

Rewrite:
- `apps/web/components/navigation/MobileBottomNav.tsx`
- canonical shell navigation

Mobile bottom nav:
- Runs
- Ask
- Panel
- You
- 52px target
- `aria-current="page"`

Navigation:
- one source of truth
- maximum four primary items + one CTA
- marketing and footer derive from same registry where appropriate

Avoid:
- duplicated arrays in MarketingNavbar/HomeContent/DashboardShell

Acceptance:
- route highlighting is correct
- keyboard navigation works
- mobile safe-area works
- no navigation regressions

---

# Patchset 05 — First Run + Dashboard convergence [AGENT]

Reference:
- `screens/Consultaion First Run.dc.html`

Rewrite:
- `apps/web/app/(app)/page.tsx`
- dashboard client/components as required

First-run state:
- composer
- real example runs
- each example includes its actual outcome/verdict/confidence when available
- tapping example pre-fills question
- key setup is quiet metadata, not a checklist

Returning state:
- active run pinned at top with real current state
- same composer remains in place
- recent runs occupy the secondary area

Remove after migration:
- `FirstRunGuide`
- `OnboardingChecklist`
- `OnboardingPanel`
- `DashboardTemplatesSection`

Do not delete any component still referenced elsewhere.

Acceptance:
- authenticated user sees one coherent dashboard/first-run surface
- example click prefill works
- active run state updates
- no duplicate onboarding controls

---

# Patchset 06 — Canonical Decision Report [OURS]

Reference:
- `screens/Consultaion Decision Report.dc.html`
- existing `apps/web/components/report/*`

Create:
- `apps/web/components/report/DecisionReport.tsx`

Contract:
```ts
DecisionReport({ run, audience: 'brief' | 'record' })
```

Contexts:
- Run end: record
- Share: brief
- Export: record
- Print: record

Layout:
- dateline
- question
- facts rail
- verdict + confidence
- agreement
- divergence
- positions + judge outcome
- risks
- next actions
- provenance

Paper surface even inside ink app.

Most important constraint:
Do not lose report-integrity/fallback behavior already present in:
- `ReportGenerationFailedCard`
- `FallbackResponseCard`
- `UnstructuredSynthesisCard`
- verification state
- corruption guards

The new component must preserve truthful degraded states.

After migration:
- retire `DecisionReportShell.tsx`
- retire `DecisionReportView.tsx`
- remove only report files genuinely absorbed by the canonical component

Acceptance:
- existing report data renders identically in content, but simpler presentation
- failed/fallback/unstructured reports never fabricate verdicts
- share and export use same canonical component
- print CSS works
- mobile report is first-class

---

# Patchset 07 — Marketing rebuild + public run flow [AGENT + backend item reserved]

Reference:
- `screens/Consultaion Homepage.dc.html`
- `screens/Consultaion Marketing Pages.dc.html`

Rewrite:
- `apps/web/components/landing/HomeContent.tsx`
- marketing route composition

New order:
1. hero + one CTA + chamber
2. facts/index rail
3. full decision report
4. how it works + labelled chamber
5. trust + price + CTA

Remove/absorb:
- `ArenaAtAGlance`
- `UseCases`
- `DifferentiationSection`
- `DecisionEdgeShowcase`

Marketing:
- server render where possible
- one copy source through `t()`
- remove client auth fetch from first paint
- no disabled CTA while auth resolves
- chamber visible on mobile/tablet, lazy/fault tolerant
- replace scroll-only report jump with shareable hash

Models registry:
- Models + Leaderboard + Hall of Fame become one registry experience
- keep historical record semantics; do not represent the figures as a universal quality score
- preserve caveats

Pricing:
- index/dot-leader presentation
- Enterprise wording must reflect actual shipped state; SSO/SAML/SCIM remain roadmap if not implemented

---

# Patchset 08 — Anonymous run before signup [OURS / BACKEND]

This is a product/backend contract change, not a visual change.

Goal:
Anonymous visitor can:
1. submit a run
2. watch full streaming result
3. read the report
4. only encounter auth gate at save/share/export

Need to audit:
- `POST /debates`
- anonymous run ownership
- rate limits
- abuse controls
- server-side persistence/retention
- share-token policy
- report access
- conversion from anonymous run → account
- continuation after signup

Must NOT:
- weaken auth on private existing runs
- let anonymous clients read arbitrary run IDs
- let anonymous runs consume uncontrolled provider spend

Add explicit anonymous-run limits and ownership model.

Acceptance:
- guest can run
- guest cannot access someone else's run
- save/share/export correctly gates
- signup preserves the current anonymous run
- rate/spend controls remain enforced

---

# Patchset 09 — Dead-code removal + dependency cleanup [AGENT, only after PS02/PS06]

Potential deletions from handoff:
- old six run renderers
- duplicate report components
- duplicate model pickers
- duplicate status/empty/error components
- onboarding furniture
- nested `components/consultaion/consultaion/`

Hard duplicates called out by handoff:
- `ui/AnimatedCounter.tsx` vs `ui/animated-counter.tsx`
- `errors/ErrorBanner.tsx` vs `ui/error-banner.tsx`
- `ui/EmptyState.tsx` vs `ui/empty-state.tsx`
- parliament StatusPill vs StatusBadge
- brand wordmark vs inline Brain mark

Rule:
Delete only after repository-wide reference search proves no consumer remains.

Acceptance:
- TypeScript compile passes
- no stale imports
- bundle does not grow from the migration
- route-level dynamic loading still works

---

# Patchset 10 — Chamber + performance verification [OURS]

Relevant existing production work:
- current main already has the real chamber geometry layered over a 2D fallback
- latest production hardening measured the GLB at ~308 KB gzip and three.js at ~151 KB gzip when served
- the chamber previously suffered a missing `alabaster` palette key and a blank hero failure

Do not replace the proven fallback path blindly.

Goals:
- chamber on all relevant widths
- lazy load on constrained devices
- no hero blank if WebGL fails
- no console exception loop
- measure LCP/CLS and bundle impact
- avoid loading WebGL in reduced-motion/save-data/2G conditions

---

# Patchset 11 — Full verification / migration audit [OURS]

Test matrix:

Frontend:
- `npx tsc --noEmit`
- `npm run lint`
- Vitest
- Playwright at 430px + desktop

Runtime:
- guest/auth
- Arena live streaming
- Compare
- Debate
- Oracle
- RedTeam
- continuation
- reload during run
- SSE disconnect + polling fallback
- synthesis provisional/final
- failed provider / partial response
- report verification/fallback
- share/export/print

Security:
- auth boundaries
- public share tokens
- anonymous run isolation
- rate limits
- CSRF/session behavior
- billing/spend accounting

Performance:
- bundle-size diff against main
- no accidental eager import of all mode renderers
- mobile LCP
- chamber cost
- no redundant polling/SSE

---

# Division of labor

## Other coding agent — use branch `agent/new-ux-ui-foundation`

Own:
- PS01 semantic design system
- PS03 panel picker + common state components
- PS04 navigation/app shell
- PS05 first run/dashboard
- PS07 marketing
- PS09 cleanup after I approve the deletion list

Agent must NOT:
- redesign backend APIs
- alter billing/spend controls
- rewrite SSE transport
- alter continuation state machine
- delete old run/report components before compatibility tests
- invent mock data in production paths
- bypass i18n
- silently change auth requirements

## Me — `feat/consultaion-new-ux`

Own:
- PS02 unified runtime workspace
- PS06 canonical report
- PS08 anonymous-run backend contract
- PS10 chamber/performance integration
- PS11 final integration, audit, regression fixing

I will review/merge the agent branch rather than letting the agent delete critical legacy paths directly.

---

# Definition of done

The new branch is ready to become the next Consultaion product only when:

1. `/new` and the canonical workspace use real production run data.
2. Existing successful runs still render.
3. Arena realtime streaming works without ghost cards.
4. Compare has no fabricated verdict.
5. Debate/Oracle/RedTeam preserve their actual semantics.
6. Continuation/retry/reload remain correct.
7. One report component serves run/share/export/print.
8. Guest-run policy is implemented and abuse-controlled.
9. Mobile navigation and 430px layout pass.
10. No raw color lint violations remain in migrated components.
11. Old duplicate components are removed only after reference proof.
12. TypeScript/lint/unit/E2E checks pass.
13. Bundle/performance does not regress materially.
14. `main` remains untouched until the new branch is explicitly promoted.

## Important architectural warning

Do not interpret “one workspace” as “one giant component”.

The desired result is:

`RunWorkspace`
→ `useComposer`
→ `useRunStream`
→ `useRunReport`
→ shared presentation primitives

not another 50KB+ monolith.
