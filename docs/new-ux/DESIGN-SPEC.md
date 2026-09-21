# Consultaion New UX - Design Specification

## Visual language
Broadsheet system: Source Serif 4 throughout; paper white and near-black ink; cyan as primary spot; magenta as rare attention/divergence accent. Left aligned, asymmetric layouts. Negative space establishes hierarchy. Avoid the previous dashboard look of large gradients, glowing orbs, excessive cards and decorative shadows. Serif is the UI chrome too.

## Surfaces
Paper: marketing, decision report, print/export.
Ink: authenticated application shell and run workspace.
The decision report remains paper even inside the ink app.

## Typography
12px metadata; 14px utility; 16px body/input; 18px emphasized body/lede; 24px section heading; 32px page heading; 48px display heading.
Allowed weights: 400 regular and 600 semibold. Do not introduce 700 or 800 in the design layer.

## Interaction
Minimum touch target 44px. Primary actions 48-52px where applicable. Focus-visible uses a 2px semantic accent outline with 2px offset. Respect prefers-reduced-motion. Interactive states are token based.

## Semantic colors
paper, ink-900, spot-cyan, spot-cyan-deep, spot-cyan-lift, spot-magenta, spot-magenta-deep, spot-magenta-lift, surface, surface-raised, ink, ink-soft, ink-faint, rule, rule-strong, spot, spot-text, alarm, alarm-text, on-spot.

## Modes
Arena: independent model perspectives then synthesis.
Debate: structured cross-talk over rounds then synthesis.
Compare: independent side-by-side answers and no synthesized verdict.
Oracle: one deep-reasoning model, exactly one seat.
RedTeam: adversarial pass against a decision or draft.

Modes are parameters of one workspace, not separate pages.

## Status vocabulary
Live, Closed, Needs you, Failed.

## App shell
Mobile primary destinations: Runs, Ask, Panel, You. Four primary items maximum plus one CTA.
Shell owns navigation, run list and the loading/empty/error/offline family.

## State family
Loading: hairline/list rhythm and aria-busy.
Empty: one serif explanation and one action.
Error: what is true, what was tried, reference code and retry.
Offline: explicitly say the run continues server-side.
Drawer: role=dialog, aria-modal=true, focus trap; backdrop/drawer/navigation must not all share one z-index.

## PanelPicker
One canonical data model with inline composer and sheet presentations. Minimum two models except Oracle. Maximum follows the mode descriptor. Use the real model registry.

## Run Workspace
Mobile order: question, verdict/confidence, full report action, panel rows, divergence. Desktop target: panel left, verdict right. Partial responses are real states; do not create ghost cards. Do not fabricate verdicts while synthesis is incomplete.

## Decision Report
One artifact with audience brief or record. Run end uses record; share uses brief; export and print use record. Content: dateline, question, facts, verdict, confidence, agreement, divergence, positions and judge outcomes, risks, next actions, provenance/integrity.

## First Run / Dashboard
One screen for both first-run and returning users. First run is composer plus three real examples with outcomes. Returning state pins the active run and keeps the composer in the same place. No checklist/progress furniture.

## Marketing
Five main sections: hero plus one CTA, full decision report, how the panel works plus chamber, trust/security, pricing plus one CTA. Models/Leaderboard/Hall of Fame become one model registry. Enterprise must not imply SSO/SAML/SCIM are shipped unless they really are.