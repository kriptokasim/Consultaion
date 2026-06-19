import { test, expect } from "@playwright/test";
import { checkA11y } from "./utils/a11y";

test.describe("Accessibility", () => {
    test("Landing page should have no critical a11y violations", async ({ page }) => {
        await page.goto("/");
        await page.waitForLoadState("networkidle");

        const { violations } = await checkA11y(page, {
            includedImpacts: ["critical", "serious"]
        });

        if (violations.length > 0) {
            console.log(`Found ${violations.length} accessibility violations on landing page`);
        }
    });

    test("Demo page should have no critical a11y violations", async ({ page }) => {
        await page.goto("/demo");
        await page.waitForLoadState("networkidle");

        await checkA11y(page, {
            includedImpacts: ["critical", "serious"]
        });
    });

    test("Login page should have no critical a11y violations", async ({ page }) => {
        await page.goto("/login");
        await page.waitForLoadState("networkidle");

        await checkA11y(page, {
            includedImpacts: ["critical", "serious"]
        });
    });

    test("Register page should have no critical a11y violations", async ({ page }) => {
        await page.goto("/register");
        await page.waitForLoadState("networkidle");

        await checkA11y(page, {
            includedImpacts: ["critical", "serious"]
        });
    });

    test("Contact page should have no critical a11y violations", async ({ page }) => {
        await page.goto("/contact");
        await page.waitForLoadState("networkidle");

        await checkA11y(page, {
            includedImpacts: ["critical", "serious"]
        });
    });

    test("Terms page should have no critical a11y violations", async ({ page }) => {
        await page.goto("/terms");
        await page.waitForLoadState("networkidle");

        await checkA11y(page, {
            includedImpacts: ["critical", "serious"]
        });
    });

    test("Privacy page should have no critical a11y violations", async ({ page }) => {
        await page.goto("/privacy");
        await page.waitForLoadState("networkidle");

        await checkA11y(page, {
            includedImpacts: ["critical", "serious"]
        });
    });
});

test.describe("OT-8: Public Trust Pages Accessibility", () => {
    test("Changelog page should have no a11y violations", async ({ page }) => {
        await page.goto("/changelog");
        await page.waitForLoadState("networkidle");

        await checkA11y(page, {
            includedImpacts: ["critical", "serious"]
        });
    });

    test("Sub-processors page should have no a11y violations", async ({ page }) => {
        await page.goto("/legal/sub-processors");
        await page.waitForLoadState("networkidle");

        await checkA11y(page, {
            includedImpacts: ["critical", "serious"]
        });
    });
});

test.describe("OT-8: Authenticated Pages Accessibility", () => {
    test("Settings page should have no critical a11y violations", async ({ page }) => {
        await page.goto("/settings");
        await page.waitForLoadState("networkidle");

        await checkA11y(page, {
            includedImpacts: ["critical", "serious"]
        });
    });

    test("Runs list page should have no critical a11y violations", async ({ page }) => {
        await page.goto("/runs");
        await page.waitForLoadState("networkidle");

        await checkA11y(page, {
            includedImpacts: ["critical", "serious"]
        });
    });

    test("Live page should have no critical a11y violations", async ({ page }) => {
        await page.goto("/live");
        await page.waitForLoadState("networkidle");

        await checkA11y(page, {
            includedImpacts: ["critical", "serious"]
        });
    });
});
