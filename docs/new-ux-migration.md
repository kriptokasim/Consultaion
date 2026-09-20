# Consultaion New UX — Migration Notes

This branch is the side-by-side implementation of the 2026-09-18 Broadsheet handoff.

## Current state

- Branch: `feat/consultaion-new-ux`
- Main is untouched.
- New design tokens live in `apps/web/styles/tokens.css`.
- New presentation styles live in `apps/web/styles/new-ux.css`.
- `apps/web/lib/modes.ts` defines the five handoff modes.
- `/new` is the first functional unified workspace route.
- The workspace reuses the existing `startDebate` API, `useRunWorkspace` SSE/recovery state, persisted responses, and synthesis state.

## Migration rule

Do not delete the existing mode renderers simply because the visual design has one workspace.

The current backend still exposes mode-specific semantics and the existing UI has recovery, billing, voting, report, and event handling accumulated over many hardening passes. The first unified workspace therefore acts as a presentation adapter.

Once the adapter covers:
- live model responses,
- synthesis/provisional/final states,
- Compare's no-verdict contract,
- Debate/Parliament round semantics,
- Oracle single-model constraints,
- RedTeam adversarial semantics,
- retry/continuation recovery,
- report/export/share provenance,

then the old renderer can be removed one mode at a time.

## Known current limitation

The existing `POST /debates` path still uses the current authentication contract. Anonymous-run-before-signup is therefore intentionally not faked in this branch yet. That is a backend/product-contract change, not a CSS/UI change.

## Next implementation order

1. Split `useRunWorkspace` into composer / stream / report seams without changing wire contracts.
2. Add the canonical app shell and four-tab mobile navigation.
3. Replace the existing report shell/view pair with the single paper report component.
4. Move the marketing landing page to the Broadsheet information architecture.
5. Add real model picker adapters using the repository's current model registry.
6. Migrate existing mode-specific behavior behind the unified workspace.
7. Add end-to-end coverage for realtime, continuation recovery, Compare, and report provenance.
8. Remove superseded presentation components only after those tests pass.
