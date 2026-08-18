# Investor / Acquisition Release Checklist

Use this checklist before sharing repository access, a diligence tag, or a production demo with an investor or strategic acquirer.

## Source control and IP

- [ ] Core repository visibility matches the chosen IP strategy.
- [ ] LICENSE, README and website messaging are consistent.
- [ ] No secrets or private credentials exist in current history/release artifacts.
- [ ] Open-source dependency inventory is available.
- [ ] Contributor/IP ownership is documented for all material code.

## Pull requests and branch state

- [ ] No unresolved P0/P1 engineering PR is sitting outside the release.
- [ ] PR #49 has been merged after validation, closed, or explicitly superseded.
- [ ] Release branch is based on the current intended production main SHA.
- [ ] No unreviewed emergency changes are included.

## Required quality gates

- [ ] Backend lint passes.
- [ ] Backend type check passes.
- [ ] Backend test suite passes.
- [ ] Backend coverage meets the repository threshold.
- [ ] Postgres integration tests pass.
- [ ] Alembic migration/schema-drift checks pass.
- [ ] Frontend type check passes.
- [ ] Frontend unit tests pass.
- [ ] Production frontend build passes.
- [ ] E2E/mobile smoke suite passes.
- [ ] OpenAPI drift check passes.
- [ ] Translation parity check passes.

## Security gates

- [ ] Gitleaks passes.
- [ ] CodeQL/SAST passes.
- [ ] Python dependency audit passes.
- [ ] npm dependency audit passes at the accepted severity threshold.
- [ ] Security headers/CSP smoke checks pass in production.
- [ ] Authentication and authorization regression suite passes.
- [ ] BYOK credentials are not logged or returned in APIs.

## Production verification

- [ ] Signup/login works on production.
- [ ] Google OAuth works if presented in the demo.
- [ ] Arena completes with real providers.
- [ ] Responses stream progressively rather than appearing only at the end.
- [ ] Failed/slow models degrade gracefully.
- [ ] Synthesis appears and persists correctly.
- [ ] Public/shareable decision report works.
- [ ] “Run this prompt yourself” flow works if enabled.
- [ ] Billing/checkout works if presented.
- [ ] Mobile flow works at 320–430 px widths.

## Operational evidence bundle

- [ ] Exact release SHA recorded.
- [ ] Release tag created.
- [ ] CI run links/evidence captured.
- [ ] Security-scan evidence captured.
- [ ] Production smoke evidence captured.
- [ ] Known-risks register reviewed and signed off.
- [ ] Architecture documentation matches release.
- [ ] API documentation matches release.
- [ ] Deployment/runbook documentation matches release.

## Investor/business telemetry

- [ ] Weekly active users reported.
- [ ] First-to-second-run retention reported.
- [ ] Share rate reported.
- [ ] Public report view → signup conversion reported.
- [ ] Free → paid conversion reported when applicable.
- [ ] Cost per run reported.
- [ ] Gross-margin estimate reported.
- [ ] Median run latency reported.
- [ ] Model/provider failure rate reported.

## Data-room packaging

- [ ] Executive summary.
- [ ] VC pitch deck.
- [ ] Strategic acquisition deck.
- [ ] Product overview and demo script.
- [ ] Technical diligence summary.
- [ ] Security overview.
- [ ] Known risks and mitigations.
- [ ] Architecture/API docs.
- [ ] Pricing and unit-economics model.
- [ ] KPI snapshot.
- [ ] Roadmap.
- [ ] Legal/IP ownership package.

## Release sign-off

A release is **Investor Demo Ready** only when there are no unresolved P0 items and all mandatory production/security/quality gates above have evidence tied to the same release SHA.
