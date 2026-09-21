# Claude Code Audit Resolution

Source: read-only audit produced from the repository and New UX handoff.

## Accepted findings

### R1 — Initial foundation already exists
Do not restart. Build on:
- apps/web/styles/tokens.css
- apps/web/styles/new-ux.css
- apps/web/lib/modes.ts
- apps/web/app/new/page.tsx
- apps/web/components/run/RunWorkspaceNew.tsx
The /new implementation is a spike/scaffold, not production-final.

### R2 — i18n is EN + TR
Use the existing apps/web/lib/i18n/*, apps/web/locales/en.json, apps/web/locales/tr.json and npm run lint:i18n.
New UX must add every key to both locale files.
The already-landed RunWorkspaceNew hardcoded strings are technical debt and must be remediated before the route grows further.

### R3 — Type scale is resolved
Canonical New UX scale: 12 / 14 / 16 / 18 / 24 / 32 / 48px.
Weights: 400 / 600.
This supersedes the accidental 13 / 15.5 / 17 / 42 / 108 values in the initial prototype token file.
The canonical token implementation has already been corrected on feat/consultaion-new-ux.

### R4 — Chamber is frozen
Use apps/web/public/embeds/consultaion-chamber.html.
Do not rewrite it during UI migration. PS07 may integrate it; PS10 owns later performance/compatibility work.

### R5 — PS03 blocks final PS02 presentation integration
Do not create a second PanelPicker, StatusPill or ErrorBanner.
The runtime refactor can be designed independently, but the unified workspace presentation should consume the shared primitive contracts.

### R6 — Duplicate homepage needs route inspection
Two files exist:
- apps/web/app/(marketing)/page.tsx
- apps/web/app/(marketing)/home/page.tsx
Do not delete either until reachability/consumer analysis is complete. Keep / as the canonical public landing route unless repository evidence proves otherwise.

### R7 — Existing run status enum remains authoritative
Use apps/web/lib/runStatus.ts.
Map granular backend statuses to the four UI labels: Live, Closed, Needs you, Failed.
Do not replace the backend enum.

### R8 — Existing report is the starting point
DecisionReportView + DecisionReportShell contain important integrity/fallback behavior.
PS06 should extend/consolidate them rather than discard the safeguards.

### R9 — Model picker should use real registry data
Do not treat the hardcoded AVAILABLE_MODELS array in ModelPanelSheet.tsx as the long-term source of truth if the repository already exposes the model registry.
Canonical picker should consume the repository's real provider/model catalog.

### R10 — Baseline comes first
Before PS01 visual changes, capture main-route screenshots at 430x932 and desktop.
The baseline is for regression detection, not pixel-perfect scoring.

## Immediate execution order

1. PS00 baseline
2. i18n remediation for already-landed New UX
3. PS01 tokens/type/lint
4. PS03 shared UI primitives
5. PS04 navigation/app shell
6. PS02 unified workspace integration
7. PS05 first-run/dashboard
8. PS06 canonical report
9. PS07 marketing
10. PS08 anonymous runs
11. PS09 cleanup
12. PS10 chamber/performance
13. PS11 final audit

## Claude Code operating rule
Do not start broad refactors before completing the read-only mapping.
Do not delete legacy systems merely because the handoff has a replacement screen.
Do not invent missing product behavior.
