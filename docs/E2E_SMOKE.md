# E2E Smoke Tests

This document describes the end-to-end test suite for Consultaion.

## Prerequisites

```bash
# Install Playwright browsers
pnpm exec playwright install chromium
```

## Running Tests

```bash
# Run all e2e tests
pnpm test:e2e

# Run specific test file
pnpm exec playwright test apps/web/e2e/smoke.spec.ts

# Run with UI mode (interactive)
pnpm exec playwright test --ui

# Run headed (visible browser)
pnpm exec playwright test --headed
```

## Test Files

| File | Purpose |
|------|---------|
| `landing.spec.ts` | Landing page content and navigation |
| `create-debate.spec.ts` | Debate creation flow |
| `dashboard.spec.ts` | Dashboard loading and error handling |
| `smoke.spec.ts` | Quick verification of all critical pages |
| `a11y.spec.ts` | Accessibility checks |

## Smoke Tests

The `smoke.spec.ts` file contains quick checks for:

- **Frontend**: Landing, Login, Register, Demo, Pricing, Models, Terms, Privacy
- **API**: `/readyz` and `/healthz` endpoints
- **Locale**: Language switcher visibility and interaction

## Test Scenarios (Patchset 83)

| Scenario | Status |
|----------|--------|
| Dashboard loads | ✅ |
| New debate modal opens | ✅ |
| Create debate (happy path) | ✅ |
| Runs page shows progress | ✅ |
| Vote up/down | Partial |
| Locale switch | ✅ |

## Artifacts on Failure

When tests fail, Playwright saves:

- Screenshots: `test-results/*/test-failed-1.png`
- Traces: `test-results/*/trace.zip`
- Console logs: In the trace viewer

## CI Integration

Tests run automatically in CI:

```yaml
- name: Run E2E Tests
  run: pnpm test:e2e
  env:
    PLAYWRIGHT_BASE_URL: ${{ vars.PLAYWRIGHT_BASE_URL }}
```

## Production Smoke

After deploy, run production smoke tests:

```bash
# Using the script
npx ts-node scripts/prod_smoke.ts

# With custom URLs
SMOKE_BASE_URL=https://your-domain.com npx ts-node scripts/prod_smoke.ts
```

## Failure → Agent Context (Patchset 83.1)

Convert test failures to PatchTask format:

```bash
# Run tests with JSON reporter
pnpm exec playwright test --reporter=json > playwright-report/report.json

# Normalize failures to PatchTasks
npx ts-node scripts/normalize_playwright_failures.ts
```

Output: `out/playwright_patchtasks.json`
