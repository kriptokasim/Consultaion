# Consultaion Data Map

> **Purpose**: Document what Consultaion stores, why it is stored, how it is linked, and the current technical retention controls.  
> **Last Updated**: August 2026  
> **Status**: Engineering source of truth for diligence; legal review still required.

---

## 1. User Authentication & Profile

| Field / table | Purpose | Technical retention | Access |
|---|---|---|---|
| `User.id` | Stable account identifier | Retained as anonymized account record after deletion | User, Admin, System |
| `User.email` | Login and notifications | Replaced with non-routable randomized address on account erasure | User, Admin |
| `User.display_name`, `avatar_url`, `bio`, `timezone` | UI personalization | Cleared on account erasure | User, Admin |
| `User.plan` | Legacy plan marker; canonical paid entitlement is `BillingSubscription` | Retained on anonymized account record where operationally required | User, Admin, Billing |
| `User.is_active` | Account status | Account is disabled on erasure | Admin, System |
| `User.created_at`, `deleted_at` | Lifecycle / compliance evidence | Retained | Admin, System |
| `User.analytics_opt_out` | Analytics preference | Retained with account lifecycle state | User, System |

**Contains PII:** Yes. Email and user-supplied profile fields are direct identifiers or user content.

---

## 2. Decision Runs, Model Output & Derived Artifacts

Consultaion uses a normalized schema. Model output is **not** stored in a `debate.messages` JSON field.

| Field / table | Data | Default technical retention | Expiry / erasure behavior |
|---|---|---:|---|
| `Debate.prompt` | User question / decision prompt | 365 days | Replaced with `[ANONYMIZED]`; direct user/team linkage removed |
| `Debate.final_content` | Final synthesis / decision report | 365 days | Cleared |
| `Debate.final_meta` | Synthesis metadata | 365 days | Cleared |
| `Debate.config`, `panel_config`, `routing_meta` | Run configuration and routing metadata | 365 days | Cleared |
| `Message.content` | Model, delegate and synthesis output | 365 days | Replaced with `[ANONYMIZED]` |
| `Message.persona`, `Message.meta` | Response/persona metadata | 365 days | Cleared |
| `Score.score` | Numeric quality/judge score | Aggregate retention | May be retained after rationale is scrubbed |
| `Score.rationale`, `Score.meta` | Free-form judge rationale / metadata | 365 days | Rationale anonymized; metadata cleared |
| `DebateTurn.*` | Claims, position drift, moderation steering | 365 days | Content fields cleared |
| `DivergenceReport.*` | Consensus / contested claim artifacts | 365 days | Content fields cleared |
| `DebateContinuation.failure_detail_safe` | Continuation failure context | 365 days | Cleared with expired decision data |
| `DebateStageCheckpoint.*`, `DebateCheckpoint.context_meta` | Execution/recovery metadata | 365 days | Content/error/context fields and resume token cleared |
| `DebateAttempt.error_summary`, `DebateAttempt.meta` | Retry/attempt diagnostics | 365 days | Free-form fields cleared; numeric aggregate cost/token facts may remain |
| `Vote`, `VoteRecord`, `ConversationVote` | Rankings, vote JSON, user feedback/reasons | 365 days | Deleted for expired decisions |
| `RedTeamSession` linked to a debate | Proposal / critique content | 365 days | Deleted for expired decisions |
| `ChallengeSession`, `ChallengeRound` | User pushback and model revisions | 365 days | Deleted for expired decisions |
| `TerminalTransition.meta` | Terminal side-effect metadata | 365 days | Metadata cleared |
| `AdminEvent` linked to a debate | Operational diagnostic text/meta | 365 days | Message anonymized; trace/meta cleared |
| `LLMUsageLog` | Tokens, cost, provider/model, latency, errors | Usage facts retained per configured policy | Direct user link and free-form error context cleared for expired decisions |

The current application setting is `RETAIN_DEBATES_DAYS=365`. This is a configurable engineering default, **not a legal conclusion** about how long every deployment is permitted or required to retain data.

**Contains PII:** Potentially. Prompts and generated responses may contain personal, confidential, regulated, source-code, or customer-supplied information.

### Auxiliary AI modes

Account erasure covers user-owned Coding Agent, Oracle and RedTeam artifacts. However, **standalone Coding/Oracle/RedTeam content does not yet have a dedicated automatic time-based retention job** when it is not linked to an expiring Debate. This is a known diligence gap and must not be represented externally as covered by the 365-day Debate purge until a product/legal retention policy is chosen and implemented.

---

## 3. Sharing & Product Analytics

| Data | Purpose | Current handling | Diligence note |
|---|---|---|---|
| `Debate.config.is_public` | Current share/public state | Stored with the run configuration | Should move to a canonical indexed share-state model as scale grows |
| `AuditLog: debate_shared` | Share enable/disable telemetry | Retained as audit telemetry | Audit transaction persistence is covered by regression tests |
| `AuditLog: view_shared_debate` | Public artifact views | Stores event metadata; currently may contain IP address | Raw-IP attribution is a temporary proxy and should be replaced by explicit privacy-preserving referral/session IDs |
| `AuditLog: register*` | Signup attribution | Used for internal PLG funnel analysis | Current same-IP attribution is approximate, not investor-grade causal attribution |
| PostHog | Product events | Deployment/provider configuration dependent | Respect analytics opt-out and provider retention configuration |

Investor-facing funnel metrics must label IP-based referral attribution as a **proxy** until explicit referral/session identifiers are deployed.

---

## 4. Reliability, Cost & Observability

| System / table | Data | Purpose | Typical / configured retention |
|---|---|---|---|
| `LLMUsageLog` | Model/provider, tokens, cost, latency, success/fallback/retry | Unit economics and model reliability | Governed by application retention policy |
| `DebateError` | Failed/degraded run context | Support and incident diagnosis | `RETAIN_DEBATE_ERRORS_DAYS=90` |
| `AdminEvent` | Operational incidents / admin-facing event context | Operations | Debate-linked content is scrubbed with expired decisions; other events follow deployment policy |
| Sentry | Error traces | Debugging and incident response | Provider/deployment configuration |
| Langfuse | LLM traces | Quality and reliability analysis | Provider/deployment configuration |
| Prometheus / OpenTelemetry | Aggregated operational metrics/traces | Reliability and capacity | Deployment configuration |

External observability systems have their own retention/export/deletion settings. Production compliance requires aligning those provider-side settings with the application's documented policy; database cleanup alone does not delete third-party copies.

---

## 5. Admin, Support & Security Audit Data

| Table | Purpose | Default technical retention | Notes |
|---|---|---:|---|
| `SupportNote` | Internal support history | Indefinite unless `RETAIN_SUPPORT_NOTES_DAYS` is set | Can contain admin-entered user context; requires legal/policy review |
| `AuditLog` | Security/admin/product audit trail | Policy dependent | Account erasure recursively redacts known PII keys; expired debate audit metadata is cleared |
| `BillingUsage` / subscription records | Entitlement, usage and billing operations | Policy / legal retention dependent | Financial records may require retention after account deletion |
| `APIKey` / `UserProviderKey` | Authentication / BYOK credentials | Until revocation or account erasure | API keys deleted and provider keys deleted on account erasure |

Security and financial auditability can require retaining pseudonymous facts after user-facing content is deleted. Any such retention should have an explicit lawful basis and documented retention period.

---

## 6. Third-Party Data Processing

Depending on enabled providers and deployment configuration, user content or metadata may be processed by:

| Provider category | Example data | Purpose |
|---|---|---|
| LLM providers / gateways | Prompt, selected context, generated output | Model inference |
| PostHog | Product events and identifiers | Product analytics |
| Sentry | Error/trace metadata | Incident diagnosis |
| Langfuse | LLM trace metadata/content depending configuration | LLM observability |
| Vercel / application hosting | HTTP/application metadata and frontend delivery | Hosting |
| Database / Redis hosting | Application state, queues/cache | Persistence and execution |
| Stripe | Customer/subscription/payment identifiers | Billing |

A production data-processing inventory should be generated from the **actual enabled deployment configuration**, not from this list alone.

---

## 7. Account Erasure

The canonical account-erasure service is shared by immediate and scheduled GDPR deletion paths. It currently performs the following classes of action:

1. Replaces direct profile identifiers and disables the account.
2. Deletes API keys, encrypted BYOK provider keys and direct user-owned operational records.
3. Anonymizes retained decision rows and removes direct user/team linkage.
4. Scrubs or deletes normalized model output, scores, votes, debate turns and derived decision artifacts.
5. Removes coding-agent, challenge, oracle and red-team user-owned artifacts.
6. Scrubs known PII keys recursively from retained audit metadata.
7. Preserves only operational/aggregate facts that the application intentionally keeps after content removal.

Account erasure is distinct from time-based retention. Both paths must remain covered by regression tests when new content-bearing tables are introduced.

---

## 8. Default Retention Configuration

| Category | Current default |
|---|---:|
| Decision/debate content and linked challenge/red-team content | 365 days |
| Standalone Coding/Oracle/RedTeam content | No dedicated timed purge yet; account erasure applies |
| Debate errors | 90 days |
| Support notes | Indefinite unless configured |
| Usage statistics | 365 days |
| Account profile | Until erasure; anonymized lifecycle record may remain |
| Third-party observability | Provider/deployment configuration |
| Billing/financial records | Policy and applicable legal requirements |

These are **technical defaults**. Production terms, privacy notices, DPAs, customer contracts, data-residency requirements and applicable law may require shorter, longer, or purpose-specific periods.

---

## 9. Diligence Controls & Known Follow-ups

Before representing Consultaion's privacy posture externally, verify all of the following against the production deployment:

- retention jobs are actually scheduled and successfully executing;
- choose and implement timed retention for standalone Coding/Oracle/RedTeam content;
- database, backups, logs, analytics and LLM-observability providers use compatible retention periods;
- account erasure covers every newly introduced content-bearing table;
- referral attribution no longer depends on raw IP matching;
- support-note indefinite retention has an explicit policy/lawful basis;
- data-subject export and erasure tests pass against the production-equivalent schema;
- subprocessors, regions and data-transfer terms are current;
- investor/customer materials distinguish implemented technical controls from planned certifications or legal conclusions.

---

*Engineering documentation only. This document is not legal advice and must be reviewed against the actual production configuration and applicable law before being used as a privacy notice, DPA, or contractual commitment.*
