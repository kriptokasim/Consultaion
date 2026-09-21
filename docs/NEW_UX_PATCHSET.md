# Consultaion New UX — Master Patchset Plan

Target repository: kriptokasim/Consultaion

Branch map:
- main = protected production baseline
- feat/consultaion-new-ux = integration branch
- agent/new-ux-ui-foundation = optional UI-agent branch created from feat/consultaion-new-ux

## Repository-local design source

Read first:
- docs/new-ux/README.md
- docs/new-ux/DESIGN-SPEC.md
- docs/new-ux/SCREEN-SPEC.md
- docs/new-ux/DECISIONS.md
- docs/new-ux/handoff-tokens.css

These are the repository-local transcription of the supplied New UX handoff.

## Non-negotiable architecture rule

This is a presentation migration, not a backend rewrite.

Preserve:
FastAPI contracts, PostgreSQL/Alembic, Celery/Redis, auth/OAuth, billing/spend controls, provider gateway, OpenRouter/provider adapters, SSE, polling fallback, continuation/retry, synthesis lifecycle, report verification/integrity/fallback.

The new product is:
one app shell + one first-run/dashboard + one run workspace + one panel picker + one status grammar + one decision report artifact.

One workspace does not mean one giant component.

## Sequencing

### PS00 — Visual baseline [REQUIRED FIRST]
Before changing tokens or layout, capture Playwright screenshots of affected main routes at:
- 430x932
- desktop viewport

Baseline is regression evidence, not a pixel-perfect score.

### PS00.5 — Chamber compatibility freeze
Use the existing apps/web/public/embeds/consultaion-chamber.html.
Do not rewrite the chamber.
Verify the existing fallback/WebGL error handling before marketing integration.

### PS01 — Semantic design system + i18n [UI AGENT]
- semantic tokens
- Source Serif 4
- exact new UX type scale: 12/14/16/18/24/32/48
- weights 400/600
- raw-palette lint rule
- paper vs ink surface mapping
- new keys in BOTH apps/web/locales/en.json and apps/web/locales/tr.json
- use existing i18n provider/hooks/server translator
- no new locale system
- no locale suffixes in keys

### PS03 — Shared UI primitives [UI AGENT]
Canonical:
- PanelPicker
- StatusPill
- ErrorBanner
- EmptyState
- ListSkeleton
- OfflineBar

PanelPicker has one data model with inline and sheet presentations.
Minimum two models except Oracle.
Use the repository's actual model registry.
Fix drawer dialog semantics, aria-modal, focus trap and z-index separation.

### PS04 — App shell/navigation [UI AGENT]
- one nav registry
- mobile bottom nav: Runs / Ask / Panel / You
- 52px target
- aria-current
- safe-area support
- consolidate duplicate nav arrays

### PS02 — Unified Run Workspace [OURS; starts after PS03 contract is stable]
Split runtime concerns without changing wire contracts:
- useComposer
- useRunStream
- useRunReport

Preserve:
- realtime SSE
- polling fallback
- reconnection
- continuation/retry
- partial responses
- provisional/final synthesis
- provider failures
- no ghost cards

Mode behavior:
- Arena = independent fan-out + synthesis
- Compare = no synthesized verdict
- Debate = cross-talk/round semantics
- Oracle = one model
- RedTeam = adversarial semantics

Do not flatten Parliament/Debate semantics merely to fit the visual mock.

### PS05 — First Run + Dashboard [UI AGENT]
One screen for first-run and returning users.
First-run: composer + three real example runs with outcomes.
Returning: active run pinned + same composer + recent runs.
Remove onboarding furniture only after reference checks.

### PS06 — Canonical Decision Report [OURS]
One component:
DecisionReport({ run, audience: 'brief' | 'record' })

Contexts:
- run end = record
- share = brief
- export = record
- print = record

Preserve report integrity, verification, failed/fallback/unstructured states.
Report remains paper inside ink app.

### PS07 — Marketing [UI AGENT]
- hero + one CTA
- report as primary differentiation
- how-it-works + chamber
- trust/security
- pricing + one CTA
- Models/Leaderboard/Hall of Fame -> one registry
- all copy through existing i18n
- server-render where possible
- no fake metrics/models/claims
- chamber visible on relevant widths and lazily/fault-tolerantly integrated
- hash navigation instead of scroll-only state

### PS08 — Anonymous run contract [OURS / BACKEND]
Guest:
run -> stream -> report -> save/share/export auth gate.

Must preserve ownership isolation, rate limits, spend controls, retention, share-token policy and post-signup transfer.

### PS09 — Dead-code cleanup [UI AGENT, only after PS02/PS06]
Delete duplicates only after repository-wide reference search + tests.
Candidates include duplicate workspace renderers, report shells, model pickers, onboarding components, duplicate status/error/empty components and nested duplicate directories.

### PS10 — Chamber/performance [OURS]
- lazy integration
- mobile/tablet correctness
- no blank hero on WebGL failure
- performance/bundle checks
- reduced-motion/save-data handling where useful

### PS11 — Final verification [OURS]
Run:
- tsc
- lint
- Vitest
- Playwright mobile + desktop
- realtime/reconnect/continuation regression tests
- Compare no-verdict contract
- report fallback/integrity checks
- auth/billing/security checks
- bundle/performance diff

## Work split

UI AGENT owns:
PS00, PS01, PS03, PS04, PS05, PS07, PS09.

OURS owns:
PS00.5, PS02, PS06, PS08, PS10, PS11.

Do not implement the same primitive twice.

## Deletion gate

No legacy file is deleted because a new screen exists.
Before deletion:
1. repository-wide reference search
2. route consumer search
3. behavior parity
4. tests
5. deletion note

## Source priority on conflict

1. current production runtime contract
2. supplied New UX handoff
3. this patchset
4. existing repo conventions
5. implementation judgement

Never invent unsupported backend behavior.
