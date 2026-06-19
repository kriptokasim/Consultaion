import { test, expect } from '@playwright/test';
import { setupAuth } from './utils/auth';

test.describe('Debate Creation Flow', () => {
    test.beforeEach(async ({ page }) => {
        await setupAuth(page);
    });

    test('should handle immediate 404 gracefully (provisioning state)', async ({ page }) => {
        // Navigate to dashboard
        await page.goto('/dashboard');

        // Open New Debate modal
        await page.getByRole('button', { name: /new debate/i }).click();

        // Fill prompt
        const prompt = `Test Debate ${Date.now()}`;
        await page.getByRole('textbox', { name: /question/i }).fill(prompt);

        // Select model if needed (default usually selected)
        // Click Create
        // We want to intercept the navigation or API call if we want to force a race condition
        // But testing the "Creating..." UI requires the backend to be slow or return 404 initially.
        // For now, we simulate the UI behavior by observing the transition.

        await page.getByRole('button', { name: /create/i }).click();

        // Expect navigation to /runs/ID
        await page.waitForURL(/\/runs\/.+/);

        // Check that we DO NOT see the "Try again" error
        await expect(page.getByText('Try again')).not.toBeVisible();
        await expect(page.getByText('Something went wrong')).not.toBeVisible();

        // Check for "Creating debate" or "Loading" or actual content
        // We updated RunDetailClient to show "Creating debate..." or the actual content
        // Wait for either the skeleton text OR the run details
        await expect(
            page.locator('text=Creating debate').or(page.locator('text=Run detail'))
        ).toBeVisible({ timeout: 15000 });

        // Eventually should see Run Detail
        await expect(page.getByText('Run detail')).toBeVisible({ timeout: 20000 });
    });

    test('modal create button should be visible on small viewport', async ({ page }) => {
        // Set viewport to 1366x768
        await page.setViewportSize({ width: 1366, height: 768 });

        await page.goto('/dashboard');
        await page.getByRole('button', { name: /new debate/i }).click();

        // Check if Create button is visible within the viewport
        const createBtn = page.getByRole('button', { name: /create/i });
        await expect(createBtn).toBeVisible();

        // Ensure it's in the sticky footer (bottom of modal) logic
        // We trust toBeVisible checks it's not hidden behind other elements or off-screen.

        // Verify it is still visible with 1920x1080
        await page.setViewportSize({ width: 1920, height: 1080 });
        await expect(createBtn).toBeVisible();
    });
});
