# VC & Enterprise Readiness Scorecard and Roadmap

This document serves as the canonical status checklist and future roadmap for Consultaion's technical readiness, covering both Product-Led Growth (PLG) positioning and enterprise-grade security/governance controls.

---

## 1. Product Narrative & Positioning
- [x] **Clear Value Proposition:** Shifted focus from simple multi-model chatting to producing verifiable, high-quality decision reports.
- [x] **Investor Positioning:** Documented the core narrative shift in `investor-positioning.md`.
- [x] **Defensibility Strategy:** Defined the roadmap to transition utility into a system of record in `defensibility.md`.

## 2. Product-Led Growth (PLG) Funnel
- [x] **Frictionless Activation:** Unauthenticated users can try the interactive `/demo` playground and transition to signup, prefilling their composer state.
- [x] **Shareable Artifacts:** Support generating unique, read-only public URLs for exported debate reports.
- [x] **Social Discovery:** Implemented dynamic Open Graph (OG) image generation via `/api/og` to increase virality on platforms.

## 3. Identity & Access Management (IAM)
- [x] **Basic Team Isolation:** Multi-tenant database design ensuring team-scoped access controls.
- [ ] **SAML 2.0 / OIDC Single Sign-On (SSO):** (Planned) Integrations with enterprise identity providers (Okta, Azure AD, Ping Identity).
- [ ] **SCIM User Provisioning:** (Planned) Automated user lifecycle management synced directly from the IdP.
- [ ] **Granular Role-Based Access Control (RBAC):** (Planned) Org Admin, Workspace Admin, Editor, and Viewer roles.

## 4. Compliance & Auditing
- [x] **Basic Auditing:** Log critical user actions (e.g. signup, login, key creation) in local database tables.
- [ ] **SOC2 Compliance:** (Planned) Formal auditing process and policy implementation.
- [ ] **Comprehensive Audit Logs:** (Planned) State-mutating trail (timestamp, actor, IP, resource) exportable via CSV/JSON.
- [ ] **Data Residency & Retention:** (Planned) Options for EU-only data residency and configurable auto-delete policies.

## 5. Security & Privacy Hardening
- [x] **Rate Limiting & Abuse Prevention:** Implemented IP-based and token-based rate limits on backend routers.
- [x] **PII Scrubbing:** Built-in pattern-based scrubber to strip sensitive personal details from LLM requests.
- [ ] **Bring Your Own Key (BYOK) Encryption:** (Planned) Allow enterprise clients to encrypt prompts/responses using their own KMS.
- [ ] **Custom DLP Rules:** (Planned) Custom regex-based Data Loss Prevention (DLP) rules for industries like healthcare (HIPAA) or finance (PCI).
