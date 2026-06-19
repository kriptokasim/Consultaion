import { Page, expect } from '@playwright/test';

export async function setupAuth(page: Page) {
    // If we have a saved session state, we might rely on that (not implemented here)

    const email = process.env.E2E_TEST_EMAIL || 'test@example.com';
    const password = process.env.E2E_TEST_PASSWORD || 'password123';

    await page.goto('/login');

    // Check if we are already redirected to dashboard (cookie auth)
    if (await page.getByText('Recent Debates').isVisible().catch(() => false)) {
        return;
    }

    // If on login page, fill credentials
    if (await page.getByRole('heading', { name: /Sign in/i }).isVisible()) {
        await page.getByLabel(/Email/i).fill(email);
        await page.getByLabel(/Password/i).fill(password);
        await page.getByRole('button', { name: /Sign in/i }).click();

        // Wait for navigation to dashboard
        await page.waitForURL('**/dashboard', { timeout: 15000 });
    }
}
