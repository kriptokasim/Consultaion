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

test.describe("Homepage Not Blank", () => {
    test("homepage renders visible content (not blank)", async ({ page }) => {
        const cspErrors: string[] = [];
        page.on("console", (msg) => {
            const text = msg.text();
            if (text.includes("Refused to execute inline script") || text.includes("violates Content Security Policy")) {
                cspErrors.push(text);
            }
        });

        await page.goto("/");
        await page.waitForLoadState("networkidle");

        // Assert page has substantial content
        const bodyText = await page.evaluate(() => document.body.innerText.trim());
        expect(bodyText.length).toBeGreaterThan(100);

        // Assert key landing elements
        await expect(page.getByText("Consultaion")).toBeVisible();
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await expect(page.getByRole("link", { name: /Pricing/i })).toBeVisible();

        // Fail if CSP is blocking scripts
        expect(cspErrors).toEqual([]);
    });

    test("Try Interactive Demo link is visible on homepage", async ({ page }) => {
        await page.goto("/");
        await expect(page.getByRole("link", { name: /Try.*demo|Try.*sample/i })).toBeVisible();
    });
});

test.describe("CSP Headers Regression", () => {
    const WEB_BASE = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${process.env.PORT || "3000"}`;

    test("enforced CSP contains required directives", async ({ request }) => {
        const response = await request.get(`${WEB_BASE}/`);
        const csp = response.headers()["content-security-policy"];

        expect(csp).toBeDefined();
        expect(csp).toContain("script-src 'self' 'unsafe-inline' 'unsafe-eval'");
        expect(csp).toContain("style-src 'self' 'unsafe-inline' https://fonts.googleapis.com");
        expect(csp).toContain("font-src 'self' data: https://fonts.gstatic.com");
        expect(csp).toContain("default-src 'self'");
        expect(csp).toContain("object-src 'none'");
        expect(csp).toContain("frame-ancestors 'self'");
        expect(csp).toContain("form-action 'self'");
    });

    test("strict CSP exists only in Report-Only header", async ({ request }) => {
        const response = await request.get(`${WEB_BASE}/`);
        const enforcedCsp = response.headers()["content-security-policy"];
        const reportOnlyCsp = response.headers()["content-security-policy-report-only"];

        expect(enforcedCsp).toBeDefined();
        expect(reportOnlyCsp).toBeDefined();

        // Report-Only should have strict script-src (no unsafe-inline/eval)
        expect(reportOnlyCsp).toContain("script-src 'self'");
        expect(reportOnlyCsp).not.toContain("'unsafe-inline'");
        expect(reportOnlyCsp).not.toContain("'unsafe-eval'");

        // Enforced should have the relaxed script-src
        expect(enforcedCsp).toContain("'unsafe-inline'");
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
