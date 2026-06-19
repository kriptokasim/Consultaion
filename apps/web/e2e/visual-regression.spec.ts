import { test, expect, type Page } from "@playwright/test";

const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 720 },
  { name: "mobile", width: 375, height: 812 },
];

const PAGES = [
  { name: "runs", url: "/runs" },
  { name: "settings", url: "/settings" },
];

test.describe("Visual Regression", () => {
  for (const viewport of VIEWPORTS) {
    for (const p of PAGES) {
      test(`${p.name} matches snapshot (${viewport.name})`, async ({
        page,
      }) => {
        await page.setViewportSize({
          width: viewport.width,
          height: viewport.height,
        });
        await page.goto(p.url);
        await page.waitForLoadState("networkidle");

        await expect(page).toHaveScreenshot(`${p.name}-${viewport.name}.png`, {
          maxDiffPixelRatio: 0.01,
        });
      });
    }
  }

  test("dark mode matches snapshot", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto("/runs");
    await page.waitForLoadState("networkidle");

    await expect(page).toHaveScreenshot("runs-dark.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("connection indicator visible on live view", async ({ page }) => {
    await page.goto("/runs");
    await page.waitForLoadState("networkidle");

    const indicator = await page.$("[role=status]");
    expect(indicator).toBeTruthy();
  });

  test("empty runs state matches snapshot", async ({ page }) => {
    await page.goto("/runs?empty=true");
    await page.waitForLoadState("networkidle");

    await expect(page).toHaveScreenshot("runs-empty.png", {
      maxDiffPixelRatio: 0.01,
    });
  });
});
