# Agent Task — Consultaion New UX UI Foundation

Repository: `kriptokasim/Consultaion`
Branch: `agent/new-ux-ui-foundation`
Base: `feat/consultaion-new-ux`

Read `docs/NEW_UX_PATCHSET.md` first.

You own PS01, PS03, PS04, PS05 and PS07. Do not touch backend runtime, billing, SSE transport, continuation state machine, or the canonical report implementation.

## Objective

Implement the handoff's Broadsheet UI architecture using the existing production APIs and data models. The goal is a clean, light, mobile-first presentation layer — not a second backend.

## Required work

### PS01
- semantic design tokens
- Source Serif 4
- semantic token mapping in Tailwind
- ESLint raw-palette guard
- paper vs ink surfaces
- remove obsolete marketing gradient/orb/text-shadow styles only where migrated
- preserve accessibility and existing shadcn functionality

### PS03
Create/reuse:
- `components/ui/PanelPicker.tsx`
- canonical `StatusPill`
- `ListSkeleton`
- `EmptyState`
- canonical `ErrorBanner`
- `OfflineBar`

PanelPicker must use the repository's actual model catalog. Do not invent providers/models.

Fix mobile drawer accessibility:
- role=dialog
- aria-modal
- focus trap
- distinct z-index layers

### PS04
- create `lib/nav.ts`
- make mobile bottom nav four tabs: Runs, Ask, Panel, You
- active route uses aria-current
- centralize navigation definitions
- remove duplicated nav arrays only after all references migrate

### PS05
- converge first-run and dashboard into one screen
- real example runs, real run states
- prefill example into composer
- pinned active run
- remove onboarding furniture only after reference audit

### PS07
- rebuild marketing page to handoff structure
- one CTA above fold
- server-renderable route
- all copy through i18n
- chamber visible at all widths with lazy/fault-tolerant presentation
- report as the main differentiation section
- merge Models/Leaderboard/Hall of Fame presentation into one registry experience
- pricing uses index style; never claim SSO/SAML/SCIM are shipped if they are roadmap

## Constraints

- no hardcoded English strings on i18n'd surfaces
- no raw Tailwind palette classes in migrated components
- no fake provider/model data
- no removal of old workspace/report components yet
- no API contract changes
- no billing/auth changes
- no giant replacement component
- keep components reasonably small and composable

## Verification

Run:
- `cd apps/web && npx tsc --noEmit`
- `cd apps/web && npm run lint`
- `cd apps/web && npx vitest run`

Also run targeted tests for every changed component.

Before deleting any file:
- repository-wide search for imports/references
- confirm no route uses it
- note deletions in commit message

## Deliverables

Commit in logical, reviewable commits:
1. `feat(new-ux): semantic design tokens and typography`
2. `feat(new-ux): canonical panel and UI state primitives`
3. `feat(new-ux): consolidate app navigation and mobile shell`
4. `feat(new-ux): converge first-run and dashboard`
5. `feat(new-ux): rebuild marketing surfaces`

Push all commits to `agent/new-ux-ui-foundation`.

At the end, write a concise summary of:
- files added/changed
- deletions proposed/performed
- tests run and results
- any blockers or decisions that must be reviewed before merging
