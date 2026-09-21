# Claude Code Start Here — Consultaion New UX

Repository: kriptokasim/Consultaion
Integration branch: feat/consultaion-new-ux

Before editing any code, read these files in this order:

1. docs/new-ux/README.md
2. docs/new-ux/DESIGN-SPEC.md
3. docs/new-ux/SCREEN-SPEC.md
4. docs/new-ux/DECISIONS.md
5. docs/new-ux/handoff-tokens.css
6. docs/NEW_UX_PATCHSET.md
7. docs/NEW_UX_AGENT_TASK.md
8. existing source files and tests named by the patchset

Then inspect the actual current code paths before proposing changes.

## What the supplied design means

This is a presentation-layer consolidation.

The product target is:
- one App Shell
- one First Run + Dashboard screen
- one Run Workspace for Arena, Debate, Compare, Oracle and RedTeam
- one PanelPicker
- one status vocabulary
- one state grammar
- one Decision Report component
- simplified Marketing

Do not rewrite the backend just to match the mock.

## Hard behavior constraints

Preserve:
- FastAPI contracts
- authentication/session behavior
- billing/spend accounting
- provider gateway
- OpenRouter/provider adapters
- PostgreSQL
- Celery/Redis
- SSE
- polling fallback
- continuation/retry
- synthesis lifecycle
- report verification/integrity/fallback

If the mock suggests behavior unsupported by the runtime, preserve runtime truth and document the mismatch.

## i18n

Existing locales are EN and TR only.

Use the current i18n implementation.
Add every new key to both:
- apps/web/locales/en.json
- apps/web/locales/tr.json

Do not create a new i18n layer.
Do not use locale suffixes inside keys.

## Design

Paper surface:
- marketing
- report
- print/export

Ink surface:
- app
- workspace

Typography:
12 / 14 / 16 / 18 / 24 / 32 / 48 px
weights 400 / 600

Mobile:
430px is first-class.
44px minimum targets.
Primary controls 48-52px.

Mode rule:
Compare does not synthesize a verdict.
Oracle has exactly one model.
Arena is independent fan-out then synthesis.
Debate preserves cross-talk/round semantics.
RedTeam preserves adversarial semantics.

## Chamber

Use the existing:
apps/web/public/embeds/consultaion-chamber.html

Do not replace the working chamber with a new implementation during the first UI migration.

## Sequencing

1. baseline
2. chamber compatibility freeze
3. tokens + i18n
4. shared UI primitives
5. app shell/nav
6. unified workspace integration
7. first run + dashboard
8. canonical report
9. marketing
10. anonymous-run backend work
11. cleanup
12. performance + final audit

Shared primitives must be stable before the workspace consumes them.

## Deletion rule

Never delete legacy files only because the new screen exists.

Before each deletion:
- repository-wide reference search
- route consumer check
- test check
- document the deletion

## Testing

At minimum for changed frontend:
- npx tsc --noEmit
- npm run lint
- npx vitest run

Add/maintain Playwright coverage for 430px mobile and desktop.

## Final rule

Do not invent:
- providers
- models
- scores
- verdicts
- metrics
- pricing
- security claims
- API behavior

Mock/example content in the supplied handoff is illustrative and must be replaced by real product data where the implementation reaches production.
