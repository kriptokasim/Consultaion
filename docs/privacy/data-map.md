# Consultaion Data Map

> **Purpose**: Document what data Consultaion stores, why, and for how long.  
> **Last Updated**: December 2024  
> **Status**: For legal review

---

## 1. User Authentication & Profile

| Field | Purpose | Retention | Access |
|-------|---------|-----------|--------|
| `id` (UUID) | Unique identifier | Until deletion | User, Admin |
| `email` | Login, notifications | Until deletion | User, Admin |
| `display_name` | UI personalization | Until deletion | User, Admin |
| `plan` | Service tier (Free/Pro) | Until deletion | User, Admin |
| `is_active` | Account status | Until deletion | Admin |
| `created_at` | Account age | Until deletion | User, Admin |
| `deleted_at` | Deletion timestamp | Permanent | System |
| `analytics_opt_out` | Privacy preference | Until deletion | User |

**Contains PII**: Yes (email)

---

## 2. Debates & Content

| Field | Purpose | Retention | Access |
|-------|---------|-----------|--------|
| `debate.prompt` | User question | 365 days | User, Admin |
| `debate.messages` | Agent/judge outputs | 365 days | User, Admin |
| `debate.champion` | Final synthesized answer | 365 days | User, Admin |
| `debate.status` | Completion state | 365 days | User, Admin |
| `debate.mode` | Classic/Conversation | 365 days | User, Admin |
| `debate.created_at` | Timestamp | 365 days | User, Admin |

**Contains PII**: Potentially (user-provided questions may contain personal info)

---

## 3. Telemetry & Observability

| System | Data | Purpose | Retention | Access |
|--------|------|---------|-----------|--------|
| **PostHog** | Events (page views, actions) | Product analytics | 90 days | System |
| **Langfuse** | LLM traces (model, tokens, latency) | Reliability | 90 days | System |
| **Sentry** | Error traces | Debugging | 30 days | System |
| **Application Logs** | Request/response metadata | Debugging | 7-30 days | System |

**Contains PII**: Minimal (user IDs, pseudonymized)

---

## 4. Admin & Support

| Table | Purpose | Retention | Access |
|-------|---------|-----------|--------|
| `SupportNote` | Internal admin notes | Indefinite | Admin only |
| `DebateError` | Failed/degraded debates | 90 days | Admin only |
| `AuditLog` | Admin action history | 365 days | Admin only |
| `BillingUsage` | Token/export counts | 365 days | Admin only |

**Contains PII**: Minimal (references user IDs)

---

## 5. Third-Party Data Sharing

| Provider | Data Shared | Purpose |
|----------|-------------|---------|
| OpenAI/Anthropic/Google | Debate prompts & messages | LLM inference |
| PostHog | Anonymized usage events | Analytics |
| Sentry | Error traces (no user content) | Error tracking |
| Render/Vercel | Application data | Hosting |

> **Note**: LLM providers receive user prompts for processing. See their privacy policies.

---

## 6. User Rights

- **Access**: Users can view their debates and account info
- **Deletion**: Users can delete their account via Settings
- **Opt-out**: Users can disable analytics tracking
- **Contact**: <privacy@consultaion.ai> (or support email)

---

## 7. Retention Summary

| Category | Default Retention |
|----------|-------------------|
| User accounts | Until user deletion |
| Debates | 365 days |
| Debate errors | 90 days |
| Support notes | Indefinite |
| Usage stats | 365 days |
| Telemetry | 90 days |

---

*This document is for internal reference and legal review. Not legal advice.*
