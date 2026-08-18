# Consultaion Known Risks and Mitigations

_Last reviewed: 2026-08-18_

This document is the canonical investor/acquirer-facing engineering risk register. It is intentionally conservative: unresolved risks are disclosed with mitigation and acceptance criteria rather than hidden.

## Severity model

- **P0** — blocks diligence release or creates material security/data/reliability risk.
- **P1** — material product/enterprise risk that should be closed before broad enterprise deployment.
- **P2** — important improvement that does not block early-stage diligence.

## Open risks

### P0 — Release candidate is not yet cleanly attested

**Status:** Open

**Evidence:** PR #49 is open and mergeable, but its PR-triggered CI, CodeQL, Docker Smoke Test and Gitleaks workflow runs are in `action_required` state. The available CI job listing is empty, so there is not enough evidence to classify this as a code/test failure.

**Impact:** An investor or strategic acquirer reviewing the repository may interpret the state as incomplete release governance.

**Mitigation:** Resolve workflow approval/policy state, execute all required checks, merge or supersede the PR, then tag the validated SHA.

**Exit criteria:** Required checks green on the release SHA; production smoke pass; release tag created.

---

### P0 — Public repository posture vs proprietary IP strategy

**Status:** Open decision

**Evidence:** The repository is currently public while the license states proprietary/confidential terms.

**Impact:** Source availability can weaken perceived IP control, complicate diligence messaging and expose implementation details unnecessarily.

**Mitigation options:**

1. Make the core product repository private and expose only SDK/examples/demo repositories; or
2. Deliberately adopt an open-core strategy with a clearly separated proprietary layer and updated licensing narrative.

**Exit criteria:** One IP strategy is formally selected; website, README, license and repository visibility are consistent with it.

---

### P1 — Investor metrics exist as definitions, not yet as a canonical live dashboard

**Status:** Open

**Impact:** The company cannot yet demonstrate activation, retention, sharing, virality, model reliability and unit economics from one trusted source.

**Mitigation:** Build a canonical investor KPI board using PostHog/admin metrics and a weekly snapshot export.

**Exit criteria:** Dashboard shows at minimum activation funnel, WAU, second-run retention, share rate, public-view-to-signup conversion, cost/run, gross-margin estimate, model failure rate and median run latency.

---

### P1 — Multi-model COGS can scale faster than revenue

**Status:** Open / manageable

**Impact:** Arena/Debate naturally consume several inference calls plus synthesis; heavy hosted usage can compress gross margin.

**Mitigation:** BYOK free tier, hosted-credit caps, model routing by task complexity, caching where valid, cost telemetry per run, and plan-level usage limits.

**Exit criteria:** Cost-per-run and contribution-margin metrics are tracked and reviewed by plan/model mix.

---

### P1 — Enterprise IAM controls are incomplete

**Status:** Roadmap

**Impact:** Larger customers may require SSO/SAML, SCIM, granular RBAC and administrative auditability before procurement.

**Mitigation:** Keep enterprise claims scoped to implemented controls; publish roadmap and prioritize SSO/RBAC/audit export before large-enterprise launch.

**Exit criteria:** Defined enterprise baseline implemented and regression-tested.

---

### P1 — Compliance claims must remain precise

**Status:** Ongoing governance

**Impact:** Readiness documents can be mistaken for certification if messaging is imprecise.

**Mitigation:** Explicitly label SOC 2/privacy/security material as readiness/planning unless formal certification exists.

**Exit criteria:** Website, pitch deck and diligence docs use consistent non-certification language.

---

### P2 — Product can be perceived as a multi-model wrapper

**Status:** Strategic risk

**Impact:** Weak positioning lowers valuation and makes the product look easily replicable.

**Mitigation:** Build the Decision Graph/system-of-record layer: assumptions, disagreements, verdicts, evidence, risks, follow-up actions and outcomes. Emphasize auditable decision workflow rather than side-by-side chat.

**Exit criteria:** Product demo and deck center on decision memory/verification, not model comparison alone.

---

### P2 — Provider dependency and policy changes

**Status:** Ongoing

**Impact:** API policy, model availability, pricing or rate limits can change.

**Mitigation:** Maintain model-agnostic gateway, OpenRouter/direct-provider options, BYOK and graceful provider failure handling.

**Exit criteria:** No single provider is required for the core product to function.

## Risk review cadence

- Review before every investor/acquirer data-room refresh.
- Review before every tagged diligence release.
- Promote any production security/data-loss issue immediately to P0.
- Keep closed risks in release notes rather than deleting history.
