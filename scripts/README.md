# Scripts - Error Intake & Self-Healing Pipeline

This directory contains TypeScript scripts for automated error detection, normalization, and PR creation.

## Quick Start

```bash
# 1. Fetch errors from Sentry
SENTRY_AUTH_TOKEN="xxx" SENTRY_ORG="your-org" SENTRY_PROJECT="your-project" \
  npx tsx scripts/sentry_errors.ts --limit 20

# 2. Normalize to PatchTasks
npx tsx scripts/normalize_errors.ts

# 3. Preview PRs (dry run)
GITHUB_TOKEN="xxx" GITHUB_OWNER="xxx" GITHUB_REPO="xxx" \
  npx tsx scripts/agent_patch_pr.ts --dry-run
```

## File Structure

```
scripts/
├── README.md                       # This file
├── patchtask.schema.json           # JSON Schema for PatchTask format
├── sentry_errors.ts                # Fetch issues from Sentry API
├── normalize_errors.ts             # Sentry → PatchTask conversion
├── ownership.ts                    # Classification rules (area/owner/severity)
├── normalize_playwright_failures.ts # Playwright → PatchTask conversion
├── prod_smoke.ts                   # Production endpoint health check
└── agent_patch_pr.ts               # Auto-create GitHub draft PRs
```

## Environment Variables

### Sentry Scripts

| Variable | Required | Description |
|----------|----------|-------------|
| `SENTRY_AUTH_TOKEN` | Yes | API token from sentry.io/settings/account/api/auth-tokens |
| `SENTRY_ORG` | Yes | Organization slug (e.g., `consultaion`) |
| `SENTRY_PROJECT` | Yes | Project slug (e.g., `python-fastapi`) |

### GitHub PR Script

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | Personal access token with `repo` scope |
| `GITHUB_OWNER` | Yes | Repository owner |
| `GITHUB_REPO` | Yes | Repository name |

### Smoke Test Script

| Variable | Required | Description |
|----------|----------|-------------|
| `SMOKE_BASE_URL` | No | Frontend URL (default: `https://consultaion.vercel.app`) |
| `SMOKE_API_URL` | No | API URL (default: `https://consultaion.onrender.com`) |

## PatchTask Schema

The normalized output follows this structure:

```typescript
interface PatchTask {
  id: string;           // e.g., "sentry-84294390"
  title: string;        // Error title/message
  area: string;         // "frontend" | "backend" | "infra"
  owner: string;        // "dashboard" | "auth" | "billing" | etc.
  severity: string;     // "blocker" | "high" | "medium" | "low"
  frequency: number;    // Occurrence count
  lastSeen: string;     // ISO timestamp
  firstSeen: string;    // ISO timestamp
  evidence: {
    sentryUrl?: string;
    stack?: string[];
    breadcrumbs?: string[];
    playwrightTest?: string;
    testFile?: string;
  };
  expectedFix: {
    kind: string;       // "guardrail" | "bugfix" | "refactor"
    filesHint: string[];// Suggested files to check
    notes: string;      // Suggested fix description
  };
}
```

## Classification Rules (ownership.ts)

The normalizer uses pattern matching to classify errors:

```typescript
// Area classification (by file path)
/apps\/web/           → frontend
/apps\/api/           → backend
/scripts|\.github/    → infra

// Owner classification (by path or error content)
/dashboard/           → dashboard
/auth|login|register/ → auth
/billing|stripe/      → billing
/debates|runs/        → debates

// Severity classification (by error type)
/login.*loop|auth.*crash/ → blocker
/TypeError|ReferenceError/ → high
/rate.*limit|429/          → medium
/deprecation|warning/      → low
```

## Output Files

Scripts write to `out/` directory:

| File | Source | Description |
|------|--------|-------------|
| `sentry_errors.json` | sentry_errors.ts | Raw Sentry API response |
| `patchtasks.json` | normalize_errors.ts | Normalized PatchTask array |
| `playwright_patchtasks.json` | normalize_playwright_failures.ts | Test failure PatchTasks |

## CI/CD Integration

See `.github/workflows/`:

- `smoke.yml` - Runs prod_smoke.ts after deploy
- `self-healing.yml` - Weekly Sentry → PR pipeline

## For Coding Agents

When consuming `patchtasks.json`:

1. **Filter by severity**: Start with `blocker` and `high`
2. **Check filesHint**: Suggested files to investigate
3. **Use sentryUrl**: Link to full Sentry issue details
4. **Check frequency**: Prioritize high-frequency issues

Example agent prompt:

```
Read out/patchtasks.json and fix the highest severity issue.
Use the filesHint to locate relevant code.
Check the sentryUrl for full stack trace if needed.
```

## Related Documentation

- [docs/ERROR_INTAKE.md](../docs/ERROR_INTAKE.md) - Pipeline overview
- [docs/OWNERSHIP.md](../docs/OWNERSHIP.md) - Classification details
- [docs/SELF_HEALING.md](../docs/SELF_HEALING.md) - Automated PR workflow
