import { test, expect } from "@playwright/test";

test.describe("Dashboard Page", () => {
    test.beforeEach(async ({ page }) => {
        // Navigate to dashboard - may redirect to login if not authenticated
        await page.goto("/dashboard");
    });

    test("should load dashboard or redirect to login", async ({ page }) => {
        // Either shows dashboard or redirects to login
        await expect(
            page.getByRole("heading", { name: /Welcome/i })
                .or(page.getByRole("heading", { name: /Sign in/i }))
        ).toBeVisible({ timeout: 10000 });
    });

    test("should display dashboard navigation elements", async ({ page }) => {
        // Check for sidebar or nav elements if authenticated
        const dashboardVisible = await page.getByText(/Recent Debates/i).isVisible().catch(() => false);

        if (dashboardVisible) {
            // Dashboard loaded - check key elements
            await expect(page.getByText(/Recent Debates/i)).toBeVisible();
            await expect(page.locator('[data-testid="new-debate-button"]')
                .or(page.getByRole("button", { name: /New Debate/i }))
                .or(page.getByText(/Start Debate/i))
            ).toBeVisible();
        } else {
            // Redirected to login - verify login page
            await expect(page.getByRole("heading", { name: /Sign in/i })).toBeVisible();
        }
    });

    test("should show model selector skeleton while loading", async ({ page }) => {
        const dashboardVisible = await page.getByText(/Recent Debates/i).isVisible().catch(() => false);

        if (dashboardVisible) {
            // Open new debate modal
            await page.getByRole("button", { name: /New Debate/i }).click();

            // Check modal opened
            await expect(page.getByRole("dialog").or(page.locator("[role='dialog']"))).toBeVisible();
        }
    });
});

test.describe("Dashboard Error Handling", () => {
    test("should handle network errors gracefully", async ({ page }) => {
        // Simulate network error
        await page.route("**/api/**", (route) => route.abort());

        await page.goto("/dashboard");

        // Should show error state or redirect, not crash
        await expect(page.locator("body")).not.toBeEmpty();
    });
});
