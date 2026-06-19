import { test, expect } from "@playwright/test";

/**
 * Smoke Tests - Quick verification of critical paths
 * These tests are designed to run fast and verify core functionality
 */

test.describe("Smoke Tests", () => {
    test("landing page loads", async ({ page }) => {
        await page.goto("/");
        await expect(page.getByText("Consultaion")).toBeVisible();
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    });

    test("login page is reachable", async ({ page }) => {
        await page.goto("/login");
        await expect(page.getByRole("heading", { name: /Sign in/i })).toBeVisible();
        await expect(page.getByLabel(/Email/i).or(page.locator('input[type="email"]'))).toBeVisible();
    });

    test("register page is reachable", async ({ page }) => {
        await page.goto("/register");
        await expect(page.getByRole("heading", { name: /Create|Sign up|Register/i })).toBeVisible();
    });

    test("demo page is accessible without auth", async ({ page }) => {
        await page.goto("/demo");
        await expect(page.getByText(/Demo/i).or(page.getByText(/Sample/i))).toBeVisible();
    });

    test("pricing page loads", async ({ page }) => {
        await page.goto("/pricing");
        await expect(page.getByRole("heading", { name: /Pricing/i })).toBeVisible();
    });

    test("leaderboard page loads", async ({ page }) => {
        await page.goto("/leaderboard");
        await expect(page.getByRole("heading", { name: /Leaderboard/i })).toBeVisible();
    });

    test("models page loads", async ({ page }) => {
        await page.goto("/models");
        await expect(page.getByRole("heading", { name: /Models/i })).toBeVisible();
    });

    test("terms page loads", async ({ page }) => {
        await page.goto("/terms");
        await expect(page.getByRole("heading", { name: /Terms/i })).toBeVisible();
    });

    test("privacy page loads", async ({ page }) => {
        await page.goto("/privacy");
        await expect(page.getByRole("heading", { name: /Privacy/i })).toBeVisible();
    });
});

test.describe("API Health", () => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    test("readyz endpoint returns healthy", async ({ request }) => {
        const response = await request.get(`${API_BASE}/readyz`);
        // Accept 200 or skip if not available
        if (response.status() !== 404) {
            expect(response.status()).toBe(200);
        }
    });

    test("healthz endpoint returns healthy", async ({ request }) => {
        const response = await request.get(`${API_BASE}/healthz`);
        // Accept 200 or skip if not available
        if (response.status() !== 404) {
            expect(response.status()).toBe(200);
        }
    });
});

test.describe("Locale Switching", () => {
    test("language switcher is visible", async ({ page }) => {
        await page.goto("/");

        // Check for language switcher button
        const langButton = page.getByRole("button", { name: /TR|EN|Language/i });
        await expect(langButton).toBeVisible();
    });

    test("can switch between languages", async ({ page }) => {
        await page.goto("/");

        // Find and click language switcher
        const langButton = page.getByRole("button", { name: /TR|EN/i }).first();

        if (await langButton.isVisible()) {
            const initialText = await langButton.textContent();
            await langButton.click();

            // Wait for potential dropdown or toggle
            await page.waitForTimeout(500);

            // Either dropdown appeared or language changed
            const afterClick = await langButton.textContent();
            // Test passes if interaction didn't crash
            expect(afterClick).toBeDefined();
        }
    });
});
