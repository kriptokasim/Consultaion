# Consultaion E2E Testing Guide

## Running Tests

### Prerequisites

- Playwright browsers must be installed
- Next.js dev server should be running

### Install Playwright Browsers

```bash
npx playwright install chromium
```

### Run Tests

**All E2E tests:**

```bash
cd apps/web
npm run test:e2e
```

**Specific test file:**

```bash
npx playwright test landing.spec.ts
```

**With UI mode (interactive):**

```bash
npx playwright test --ui
```

**Debug mode:**

```bash
npx playwright test --debug
```

## Test Structure

### Landing Page Test (`landing.spec.ts`)

Covers:

- ✅ Navbar visibility and navigation links
- ✅ Hero section with CTA
- ✅ "How it Works" 4-step section
- ✅ Demo CTA button
- ✅ Feature cards
- ✅ Multi-LLM section with benefits
- ✅ Footer links (Terms, Privacy, Contact)
- ✅ Language switcher
- ✅ Sticky navbar on scroll

### Create Debate Test (`create-debate.spec.ts`)

Existing test for debate creation flow.

### Accessibility Tests (`a11y.spec.ts`)

Automated WCAG 2.1 AA compliance checks using @axe-core/playwright:

- ✅ Landing page
- ✅ Demo page
- ✅ Login/Register pages
- ✅ Contact, Terms, Privacy pages
- Checks for critical and serious accessibility violations
- Fails tests if violations are found

**Run only accessibility tests:**

```bash
npx playwright test a11y.spec.ts
```

## Common Issues & Solutions

### Issue: Browser Not Found

**Solution:**

```bash
npx playwright install
```

### Issue: Port Already in Use

**Solution:**
Make sure no other process is using port 3000, or set a different port:

```bash
PORT=3001 npx playwright test
```

### Issue: Tests Timeout

**Solution:**

- Ensure dev server is running (`npm run dev`)
- Increase timeout in `playwright.config.ts` if needed
- Check network connectivity

## CI/CD Integration

Tests are configured to run in CI with:

- Retries: 1 (only in CI)
- Screenshot: on-failure only
- Trace: retain-on-failure
- Reporter: GitHub Actions + HTML

## Writing New Tests

1. Create new `.spec.ts` file in `apps/web/e2e/`
2. Import test utilities:

   ```typescript
   import { test, expect } from "@playwright/test";
   ```

3. Use descriptive test names
4. Always include `beforeEach` for navigation
5. Use accessible selectors (roles, labels) when possible

## Best Practices

- ✅ Use semantic selectors (`getByRole`, `getByLabel`)
- ✅ Add `await` for all async operations  
- ✅ Use `scrollIntoViewIfNeeded()` before clicking elements below fold
- ✅ Verify navigation with `expect(page).toHaveURL()`
- ✅ Add waits for dynamic content with `waitForTimeout()` sparingly
- ❌ Avoid brittle CSS selectors when possible
- ❌ Don't hardcode absolute URLs
