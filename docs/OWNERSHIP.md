# Component Ownership

This document defines ownership boundaries for error classification and routing.

## Overview

Errors are classified by:

- **Area**: `frontend` | `backend` | `infra`
- **Owner**: Component team responsible for the fix
- **Severity**: `blocker` | `high` | `medium` | `low`

## Ownership Map

### Frontend Components

| Owner | File Patterns | Scope |
|-------|---------------|-------|
| `dashboard` | `app/(app)/dashboard/`, `components/dashboard/` | Main dashboard, debate creation modal |
| `runs` | `app/(app)/runs/`, `components/parliament/`, `components/consultaion/` | Run pages, replay, debate view |
| `auth` | `app/(marketing)/(login|register)/`,`components/auth/` | Login, register, session |
| `settings` | `app/(app)/settings/`, `components/settings/` | User preferences, profile |
| `billing` | `components/billing/` | Subscription, usage, quotas |
| `admin` | `app/(app)/admin/` | Admin dashboard |
| `marketing` | `app/(marketing)/`, `components/landing/` | Landing pages, docs, pricing |

### Backend Components

| Owner | File Patterns | Scope |
|-------|---------------|-------|
| `auth` | `routes/auth/`, `auth/` | Authentication endpoints |
| `runs` | `routes/debates/`, `parliament/`, `agents/` | Debate API, AI orchestration |
| `voting` | `routes/votes/` | Vote endpoints |
| `billing` | `routes/billing/` | Stripe webhooks, usage |
| `admin` | `routes/admin/` | Admin API |
| `sse` | `sse/` | Real-time events |
| `db` | `models/`, `database/` | Database models, migrations |
| `api` | (default backend) | General API |

## Severity Classification

### Blocker (P0)

- Auth/login loops or failures
- Debate creation completely broken
- SSR crash preventing page load
- Session/cookie issues causing logout

### High (P1)

- Run page fails to load
- Replay functionality broken
- Voting fails silently
- 5xx errors from API
- TypeError/ReferenceError in critical paths

### Medium (P2)

- UI regressions (styling broken)
- Layout shifts
- Dark mode issues
- Missing translations
- Slow but functional features

### Low (P3)

- Console warnings
- Deprecation notices
- Minor UX polish issues
- Non-critical feature gaps

## Escalation

When an error doesn't match any pattern:

1. Default to `frontend/dashboard` or `backend/api`
2. Assign `medium` severity
3. Flag for manual review

## Updating Ownership

Edit `scripts/ownership.ts` to add new patterns:

```typescript
export const ownershipRules: OwnershipRule[] = [
  // Add new patterns here
  { pattern: /your-new-pattern/, area: 'frontend', owner: 'your-owner' },
];
```
