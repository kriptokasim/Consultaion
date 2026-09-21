# Claude Code Task — Consultaion New UX UI Foundation

Repository: kriptokasim/Consultaion
Primary integration branch: feat/consultaion-new-ux

Read docs/new-ux/CLAUDE-CODE-START.md first.
Then read:
- docs/new-ux/README.md
- docs/new-ux/DESIGN-SPEC.md
- docs/new-ux/SCREEN-SPEC.md
- docs/new-ux/DECISIONS.md
- docs/new-ux/handoff-tokens.css
- docs/NEW_UX_PATCHSET.md

## Phase 0: read-only audit

Before editing:
- inspect the current repo structure
- map each handoff screen to current routes/components
- identify current i18n files and existing keys
- inspect the current chamber embed and chamber test
- identify duplicate navigation/model/status/error/onboarding components
- identify all consumers before proposing deletion
- produce a short implementation map

Do not invent replacements during the audit.

## Assignment

Implement UI/frontend consolidation for:
PS00, PS01, PS03, PS04, PS05 and PS07.

You may prepare PS09 deletion candidates, but do not delete critical legacy workspaces/report files until behavior parity is proven.

Do NOT implement:
- anonymous-run backend work
- billing changes
- auth changes
- SSE transport changes
- continuation/retry state-machine changes
- canonical DecisionReport implementation
- backend API contract changes

## PS00

Create/maintain screenshot baseline for relevant main routes:
- 430x932
- desktop

Keep baseline artifacts documented so visual regressions can be compared later.

## PS01

Implement:
- Broadsheet semantic tokens
- Source Serif 4
- 12/14/16/18/24/32/48px scale
- 400/600 weights
- paper and ink surfaces
- semantic raw-palette lint rule

Existing i18n is EN + TR only.
Every new UI key must be in:
- apps/web/locales/en.json
- apps/web/locales/tr.json

Use existing i18n APIs.
Do not create another translation system.

## PS03

Create/reuse:
- components/ui/PanelPicker.tsx
- components/ui/StatusPill.tsx
- components/ui/ListSkeleton.tsx
- components/ui/EmptyState.tsx
- components/errors/ErrorBanner.tsx
- components/ui/OfflineBar.tsx

PanelPicker:
- one canonical model/data contract
- inline and sheet presentations
- minimum two models except Oracle
- real current model registry

Fix mobile drawer:
- role=dialog
- aria-modal=true
- focus trap
- separate backdrop/drawer/navigation stacking contexts

## PS04

Create one nav registry.
Mobile primary navigation:
- Runs
- Ask
- Panel
- You

52px navigation target and aria-current on active route.
Remove duplicated nav definitions only after all consumers are migrated.

## PS05

Converge first-run and dashboard:
- one composer
- real example runs
- example result/verdict/confidence from actual data when available
- selecting an example prefills the composer
- active run pinned
- recent runs below

No onboarding checklist/progress furniture.

## PS07

Rebuild marketing presentation:
1. hero + single primary CTA
2. decision report
3. how it works + chamber
4. trust/security
5. pricing + CTA

Use existing chamber:
apps/web/public/embeds/consultaion-chamber.html

Do NOT rewrite the chamber implementation.

Models / Leaderboard / Hall of Fame become one registry surface.
Use existing i18n for every user-facing string.
Do not use handoff example metrics as production metrics.

## Design constraints

- mobile-first at 430px
- 44px minimum interaction target
- 48-52px primary controls
- no giant gradients/orbs
- no excessive dashboard cards
- typography and whitespace establish hierarchy
- semantic cyan primary; magenta sparingly
- report and marketing are paper
- app shell/workspace are ink
- no fake models, scores, metrics or product capabilities

## Testing

After each logical change:
- cd apps/web && npx tsc --noEmit
- cd apps/web && npm run lint
- cd apps/web && npx vitest run

Add/update Playwright tests for:
- 430px
- desktop
- drawer accessibility
- navigation
- first-run composer
- panel selection
- marketing CTA

Run the repository's i18n parity check.

## Commit structure

Use logical commits:
1. feat(new-ux): add visual baseline and handoff source
2. feat(new-ux): semantic design tokens and typography
3. feat(new-ux): canonical panel and UI state primitives
4. feat(new-ux): consolidate app navigation and mobile shell
5. feat(new-ux): converge first-run and dashboard
6. feat(new-ux): rebuild marketing surfaces

## Deletion discipline

Before deleting any file:
- repository-wide reference search
- route search
- test search
- document why it is safe

## Final report

Return:
- files added/changed/deleted
- commits
- tests and results
- screenshots/baseline paths
- unresolved design/runtime conflicts
- deletion candidates not yet safe to remove
