# Consultaion New UX - Repository Design Source of Truth

This directory records the September 2026 New UX handoff inside the repository so a coding agent can work without access to the external attachment.

Target repository: kriptokasim/Consultaion
Target integration branch: feat/consultaion-new-ux

Read order:
1. docs/new-ux/README.md
2. docs/new-ux/DESIGN-SPEC.md
3. docs/new-ux/SCREEN-SPEC.md
4. docs/new-ux/DECISIONS.md
5. docs/NEW_UX_PATCHSET.md
6. existing code and tests referenced by those documents

The new UX is a presentation migration, not a backend rewrite. Preserve the current API, auth, billing, spend controls, provider gateway, SSE, polling fallback, continuation/retry, synthesis and report integrity behavior.

Product model: one app shell, one first-run/dashboard surface, one run workspace for five modes, one panel picker, one status vocabulary, one state grammar and one decision report artifact.

Do not invent data, model metrics, verdicts, API behavior or authentication behavior. Do not delete legacy renderers until behavior parity and tests exist.