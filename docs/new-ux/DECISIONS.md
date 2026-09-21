# New UX Implementation Decisions

D1 i18n: the repository already supports exactly EN and TR. Add every new key to apps/web/locales/en.json and apps/web/locales/tr.json. Use the existing i18n provider/hooks. No second i18n system.

D2 visual baseline: capture Playwright screenshots before token migration at 430x932 and a desktop viewport for affected routes. Baseline is regression evidence, not a pixel score.

D3 chamber: do not rewrite the chamber. Use apps/web/public/embeds/consultaion-chamber.html. It already has a 2D fallback and a WebGL layer with defensive failure handling. Marketing integration may wrap it, but should not replace its rendering logic.

D4 sequencing: shared primitives must stabilize before the unified workspace presentation integration. This prevents duplicate PanelPicker, StatusPill or error components.

D5 architecture: one workspace does not mean one giant component. Target presentation seams are Composer, PanelPicker, RunStatus, ModelResponses, Divergence, Verdict and ReportPreview. Runtime seams are useComposer, useRunStream and useRunReport.

D6 conflict rule: production runtime contract is authoritative; handoff visual behavior cannot justify inventing unsupported backend behavior.

D7 anonymous runs: guest execution is a backend/security feature with ownership isolation, spend limits, rate limits, retention and safe transfer to an account.

D8 cleanup: delete legacy code only after repository-wide reference search, behavior parity and passing tests.

D9 typography: 12/14/16/18/24/32/48px and weights 400/600.

D10 handoff example numbers and model metrics are illustrative. Production UI must use real data/configuration.