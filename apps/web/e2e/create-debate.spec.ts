import { test, expect } from "@playwright/test";

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

test.describe("Live debate flow", () => {
  test("runs a FAST_DEBATE session from home", async ({ page }) => {
    await page.goto("/");
    await page.fill('textarea[placeholder="Enter your debate prompt or question..."]', "Playwright smoke debate");
    await page.getByRole("button", { name: /run debate/i }).click();
    await expect(page.getByText(/Fast debate completed/i)).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Voting Simulation/i)).toBeVisible();
  });

  test("render run detail for a debate created via API", async ({ page, request }) => {
    const response = await request.post(`${API_BASE}/debates`, {
      data: { prompt: "Playwright run detail" },
    });
    expect(response.ok()).toBeTruthy();
    const payload = await response.json();
    const debateId = payload.id;
    await page.goto(`/runs/${debateId}`);
    await expect(page.getByText(/Voting Simulation/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /Export Markdown/i })).toBeVisible();
  });
});
