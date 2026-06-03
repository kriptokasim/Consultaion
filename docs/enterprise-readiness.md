# Enterprise Readiness Roadmap

To transition Consultaion from a self-serve PLG tool to an enterprise-ready platform, the following features and architectural changes are scheduled on the roadmap.

## 1. Identity & Access Management (IAM)

### Single Sign-On (SSO) & SCIM
- **SAML 2.0 / OIDC Integration:** Allow enterprise customers to use Okta, Azure AD, or Google Workspace for authentication.
- **SCIM Provisioning:** Automated user lifecycle management (provisioning/deprovisioning) synced directly from the enterprise IdP.
- **JIT Provisioning:** Just-in-time creation of team environments upon first SSO login.

### Role-Based Access Control (RBAC)
Transition from simple owner/team-member roles to granular RBAC:
- **Org Admin:** Full billing, SSO, and team management.
- **Workspace Admin:** Can configure LLM provider keys, manage custom agents/personas.
- **Editor:** Can create, start, and share debates.
- **Viewer:** Read-only access to team debates and reports.

## 2. Compliance & Auditing

### Comprehensive Audit Logs
- Log all state-mutating actions (login, prompt submission, debate share, export, provider key change).
- Exportable audit trails via UI (CSV) and API (JSON) for SIEM integration (Splunk, Datadog).
- Schema: `timestamp`, `actor_id`, `actor_ip`, `action_type`, `resource_id`, `before_state`, `after_state`.

### Data Residency & Retention Policies
- Support for EU-only data residency (routing to EU-based LLM endpoints and EU-hosted Postgres).
- Configurable data retention policies (e.g., auto-delete debates after 30, 60, or 90 days).

## 3. Advanced Billing & Quotas

### Cost Allocation & Chargebacks
- Tagging debates with `project_id` or `cost_center`.
- Granular usage dashboards showing token consumption and cost broken down by team, user, and project.

### Custom Rate Limiting
- Enterprise-specific rate limits to protect shared infrastructure while guaranteeing SLA for dedicated tenants.

## 4. Security & Privacy Hardening

### Bring Your Own Key (BYOK)
- Allow enterprises to use their own KMS (AWS KMS, Google Cloud KMS) to encrypt their prompt and response data at rest in our database.

### Custom DLP Rules
- Expand the existing PII scrubber to support custom regex and dictionary-based Data Loss Prevention (DLP) rules specific to the enterprise's industry (e.g., HIPAA, PCI-DSS).
