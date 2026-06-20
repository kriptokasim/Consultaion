import { test, expect } from "@playwright/test";

const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 720 },
  { name: "mobile", width: 375, height: 812 },
];

const PAGES = [
  { name: "runs", url: "/runs", selector: "h1" },
  { name: "settings", url: "/settings", selector: "h1" },
];

test.describe("DOM Structure Validation", () => {
  for (const viewport of VIEWPORTS) {
    for (const p of PAGES) {
      test(`${p.name} loads main structure (${viewport.name})`, async ({ page }) => {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await page.goto(p.url);
        await page.waitForLoadState("networkidle");

        const element = page.locator(p.selector).first();
        await expect(element).toBeVisible();
      });
    }
  }

  test("dark mode page renders without error", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto("/runs");
    await page.waitForLoadState("networkidle");

    const element = page.locator("h1").first();
    await expect(element).toBeVisible();
  });

  test("connection indicator visible on live view", async ({ page }) => {
    await page.goto("/live");
    await page.waitForLoadState("networkidle");

    const indicator = page.locator("[role=status]").first();
    await expect(indicator).toBeVisible();
  });

  test("empty runs state renders without error", async ({ page }) => {
    await page.goto("/runs?empty=true");
    await page.waitForLoadState("networkidle");

    const element = page.locator("main").first();
    await expect(element).toBeVisible();
  });
});
