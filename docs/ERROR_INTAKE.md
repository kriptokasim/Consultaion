# Error Intake Pipeline

This document describes how to pull production errors from Sentry, normalize them, and generate PatchTask bundles for coding agents.

## Prerequisites

1. **Sentry API Token**: Create at <https://sentry.io/settings/account/api/auth-tokens/>
2. **Environment Variables**:

   ```bash
   export SENTRY_AUTH_TOKEN="your-token"
   export SENTRY_ORG="your-org-slug"
   export SENTRY_PROJECT="consultaion"
   export SENTRY_ENV="production"  # optional, defaults to production
   ```

## Quick Start

```bash
# 1. Fetch recent errors from Sentry
pnpm sentry:pull

# 2. Normalize errors to PatchTask format
pnpm sentry:normalize
```

## Scripts

### `scripts/sentry_errors.ts`

Fetches unresolved issues from Sentry API.

```bash
# Basic usage (25 issues)
npx ts-node scripts/sentry_errors.ts

# Custom limit
npx ts-node scripts/sentry_errors.ts --limit 50

# Include full event data (slower)
npx ts-node scripts/sentry_errors.ts --with-events
```

**Output**: `out/sentry_errors.json`

### `scripts/normalize_errors.ts`

Converts raw Sentry data to PatchTask JSON.

```bash
# Basic usage (uses config defaults)
npx tsx scripts/normalize_errors.ts

# Override minimum frequency threshold
npx tsx scripts/normalize_errors.ts --min-frequency 3
```

**Output**: `out/patchtasks.json`

## Configuration

Configuration is centralized in `scripts/error-intake.config.ts`:

| Option | Default | Environment Variable | Description |
|--------|---------|---------------------|-------------|
| `minFrequency` | 2 | `SENTRY_ERROR_MIN_FREQUENCY` | Minimum occurrences to include (filters one-off errors) |
| `defaultLimit` | 10 | `SENTRY_ERROR_LIMIT` | Default Sentry fetch limit |
| `defaultSeverities` | `['blocker', 'high']` | - | Severities that trigger PR creation |

**Example**: Only include errors that occurred 3+ times:

```bash
SENTRY_ERROR_MIN_FREQUENCY=3 npm run sentry:normalize
```

## PatchTask Schema

Each normalized error becomes a PatchTask:

```json
{
  "id": "sentry-123456",
  "title": "TypeError: cannot read property...",
  "area": "frontend",
  "owner": "dashboard",
  "severity": "high",
  "frequency": 37,
  "lastSeen": "2025-12-31T18:10:00Z",
  "evidence": {
    "sentryUrl": "https://sentry.io/...",
    "stack": ["file.ts:123 in functionName"],
    "request": { "url": "/api/...", "method": "GET" }
  },
  "expectedFix": {
    "kind": "guardrail",
    "filesHint": ["apps/web/..."],
    "notes": "..."
  }
}
```

## Ownership & Severity

See `scripts/ownership.ts` for classification rules.

### Severity Levels

| Level | Criteria |
|-------|----------|
| **Blocker** | Auth loops, debate creation broken, SSR crash |
| **High** | Run page failures, voting errors, 5xx errors |
| **Medium** | UI regressions, layout shifts |
| **Low** | Console warnings, deprecations |

### Owners

| Owner | Scope |
|-------|-------|
| `dashboard` | Main dashboard, debate creation |
| `runs` | Run pages, replay, parliament |
| `voting` | Vote up/down functionality |
| `auth` | Login, register, session |
| `billing` | Stripe integration, quotas |
| `settings` | User preferences, profile |
| `admin` | Admin panel |
| `sse` | Server-sent events |
| `api` | General backend |

## Output Files

```
out/
├── sentry_errors.json   # Raw Sentry data
└── patchtasks.json      # Normalized PatchTasks (agent-ready)
```

## CI Integration

Add to GitHub Actions:

```yaml
- name: Fetch Sentry Errors
  run: npx ts-node scripts/sentry_errors.ts --limit 20
  env:
    SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
    SENTRY_ORG: ${{ secrets.SENTRY_ORG }}
    SENTRY_PROJECT: ${{ secrets.SENTRY_PROJECT }}
```
