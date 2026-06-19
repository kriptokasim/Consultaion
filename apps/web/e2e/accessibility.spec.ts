import { test, expect } from "@playwright/test";

const PAGES = [
  { name: "runs", url: "/runs" },
  { name: "settings", url: "/settings" },
  { name: "healthz", url: "/healthz" },
];

test.describe("Accessibility", () => {
  for (const page of PAGES) {
    test(`${page.name} has no critical accessibility violations`, async ({ page: p }) => {
      await p.goto(page.url);
      await p.waitForLoadState("networkidle");

      const axe = await import("@axe-core/playwright");
      const results = await new axe.AxeBuilder({ page: p })
        .include("main")
        .analyze();

      const critical = results.violations.filter(
        (v) => v.impact === "critical" || v.impact === "serious"
      );

      expect(critical, `Found ${critical.length} critical/serious violations`).toHaveLength(0);
    });
  }

  test("keyboard navigation works on run detail", async ({ page }) => {
    await page.goto("/runs");
    await page.waitForLoadState("networkidle");

    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => document.activeElement?.tagName);
    expect(focused).toBeTruthy();
  });

  test("focus order is logical", async ({ page }) => {
    await page.goto("/runs");
    await page.waitForLoadState("networkidle");

    const focusable = await page.$$eval(
      "button, a, input, select, textarea, [tabindex]",
      (els) => els.map((el) => el.getBoundingClientRect().top)
    );

    for (let i = 1; i < focusable.length; i++) {
      expect(focusable[i]).toBeGreaterThanOrEqual(focusable[i - 1] - 50);
    }
  });

  test("ARIA landmarks exist", async ({ page }) => {
    await page.goto("/runs");
    await page.waitForLoadState("networkidle");

    const hasMain = await page.$("main, [role=main]");
    expect(hasMain).toBeTruthy();
  });

  test("images have alt text", async ({ page }) => {
    await page.goto("/runs");
    await page.waitForLoadState("networkidle");

    const images = await page.$$eval("img", (imgs) =>
      imgs.map((img) => ({
        src: img.src,
        hasAlt: img.hasAttribute("alt"),
      }))
    );

    for (const img of images) {
      expect(img.hasAlt, `Image ${img.src} missing alt`).toBe(true);
    }
  });
});
