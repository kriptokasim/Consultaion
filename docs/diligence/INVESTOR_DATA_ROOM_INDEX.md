# Consultaion Investor / M&A Data Room Index

This index defines the canonical structure for investor and strategic-acquirer diligence. Keep sensitive materials outside the public repository; this file describes the structure and source-of-truth documents.

## 00 — Executive

- Executive Summary
- One-page teaser
- Company / product snapshot
- Current fundraising or transaction objective

## 01 — Product

- Product overview
- Demo script
- Example decision reports
- Product screenshots/video
- Current roadmap

## 02 — Market and positioning

- Investor positioning
- Market landscape
- Competitive map
- Category thesis: multi-model decision / verification layer
- Target user and buyer profiles

## 03 — Traction and analytics

- KPI dashboard snapshot
- Activation funnel
- Retention cohorts
- Share/viral loop metrics
- Customer/user interview summary
- Revenue and paid-pilot evidence when available

## 04 — Business model and economics

- Pricing strategy
- Cost-per-run model
- Gross-margin model
- BYOK vs hosted usage mix
- 12/24/36-month financial scenarios

## 05 — Technology

- `docs/ARCHITECTURE.md`
- `docs/diligence/TECHNICAL_DILIGENCE_SUMMARY.md`
- API overview / OpenAPI snapshot
- Release notes and stable release SHA
- Build/deploy overview

## 06 — Security and privacy

- Security overview
- `docs/diligence/SECRETS_SCAN.md`
- `docs/diligence/CI_OVERVIEW.md`
- `docs/diligence/COVERAGE.md`
- Data retention/privacy material
- Security incident/response policy if applicable

## 07 — Risk

- `docs/diligence/KNOWN_RISKS_AND_MITIGATIONS.md`
- Enterprise readiness roadmap
- Provider/platform dependency analysis
- Compliance-readiness status

## 08 — IP and legal

- License
- IP ownership / assignment evidence
- Domain/trademark ownership
- Open-source dependency inventory
- Contributor list and assignment status
- Terms/privacy documents

## 09 — Investor materials

- VC pitch deck
- Acquisition deck
- Investor FAQ
- Demo script
- Target investor list
- Strategic acquirer list
- Outreach tracker

## 10 — Release evidence

For each diligence release, retain:

- exact commit SHA
- release tag
- CI evidence
- CodeQL/SAST evidence
- Gitleaks evidence
- dependency-audit evidence
- production smoke-test evidence
- known-risks snapshot

Use `docs/diligence/INVESTOR_RELEASE_CHECKLIST.md` as the gate before publishing a new diligence snapshot.
