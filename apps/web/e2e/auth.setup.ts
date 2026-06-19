import { test as setup, expect } from '@playwright/test';
import path from 'path';

const authFile = path.join(__dirname, '../../.playwright/.auth/user.json');

setup('authenticate', async ({ page }) => {
    // If we can use a simpler auth method (like setting a token), prefer that.
    // For now, we perform the UI login flow.

    const email = process.env.E2E_TEST_EMAIL || 'test@example.com';
    const password = process.env.E2E_TEST_PASSWORD || 'password123';

    await page.goto('/login');

    if (await page.getByText('Recent Debates').isVisible().catch(() => false)) {
        await page.context().storageState({ path: authFile });
        return;
    }

    await page.getByLabel(/Email/i).fill(email);
    await page.getByLabel(/Password/i).fill(password);
    await page.getByRole('button', { name: /Sign in/i }).click();

    await page.waitForURL('**/dashboard');
    await expect(page.getByText('Recent Debates')).toBeVisible();

    await page.context().storageState({ path: authFile });
});
