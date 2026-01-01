# Self-Healing Pipeline

Automated error → fix → PR workflow for continuous improvement.

## Overview

```
Sentry Errors → Normalize → PatchTasks → Agent PR → Human Review → Merge
```

## Prerequisites

```bash
# Required environment variables
export GITHUB_TOKEN="ghp_..."     # Personal access token with repo scope
export GITHUB_OWNER="kriptokasim" # Repository owner
export GITHUB_REPO="Consultaion"  # Repository name

# For Sentry integration
export SENTRY_AUTH_TOKEN="..."
export SENTRY_ORG="..."
export SENTRY_PROJECT="consultaion"
```

## Quick Start

```bash
# 1. Pull production errors
npx ts-node scripts/sentry_errors.ts --limit 20

# 2. Normalize to PatchTasks
npx ts-node scripts/normalize_errors.ts

# 3. Preview PRs (dry run)
npx ts-node scripts/agent_patch_pr.ts --dry-run

# 4. Create draft PRs
npx ts-node scripts/agent_patch_pr.ts
```

## Pipeline Components

### Error Sources

| Source | Script | Output |
|--------|--------|--------|
| Sentry | `sentry_errors.ts` | `out/sentry_errors.json` |
| Playwright | `normalize_playwright_failures.ts` | `out/playwright_patchtasks.json` |

### Normalizer

Converts raw errors to standardized PatchTask format:

- `normalize_errors.ts` - Sentry → PatchTask
- `normalize_playwright_failures.ts` - Playwright → PatchTask

### PR Creator

`agent_patch_pr.ts` creates GitHub draft PRs with:

- Sentry/test links
- Stack traces
- Suggested files to fix
- Severity labels

## Configuration

### Severity Filtering

By default, only `blocker` and `high` severity issues create PRs:

```bash
# Only high-severity (default)
npx ts-node scripts/agent_patch_pr.ts

# All severities
npx ts-node scripts/agent_patch_pr.ts --all

# Preview without creating
npx ts-node scripts/agent_patch_pr.ts --dry-run
```

### Rate Limiting

The script limits to 5 PRs per run to avoid overwhelming reviewers.

## Human-in-the-Loop

All PRs are created as **drafts** requiring human review:

1. Review PR description and evidence
2. Check suggested files
3. Make actual code changes
4. Mark ready for review
5. Merge

## CI Integration

Add to `.github/workflows/self-healing.yml`:

```yaml
name: Self-Healing

on:
  schedule:
    - cron: '0 9 * * 1' # Weekly on Monday 9am

jobs:
  heal:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Install dependencies
        run: npm install -g ts-node typescript

      - name: Pull Sentry errors
        run: npx ts-node scripts/sentry_errors.ts --limit 10
        env:
          SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
          SENTRY_ORG: ${{ secrets.SENTRY_ORG }}
          SENTRY_PROJECT: ${{ secrets.SENTRY_PROJECT }}

      - name: Normalize errors
        run: npx ts-node scripts/normalize_errors.ts

      - name: Create PRs
        run: npx ts-node scripts/agent_patch_pr.ts
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_OWNER: ${{ github.repository_owner }}
          GITHUB_REPO: ${{ github.event.repository.name }}
```

## Security Considerations

- PRs are **draft** by default
- Human review required before merge
- Token should have minimal required permissions
- High-frequency errors are deduplicated
