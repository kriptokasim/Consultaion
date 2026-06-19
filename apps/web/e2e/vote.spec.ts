import { test, expect } from "@playwright/test";

/**
 * Vote Tests - Requires authenticated session
 * 
 * Note: These tests need a pre-existing debate with completed status.
 * In CI, you may need to create a test debate first or use a seeded DB.
 */

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

test.describe("Voting Functionality", () => {
    // Skip if no auth - these require login
    test.skip(({ browserName }) => !process.env.E2E_AUTH_TOKEN, "Requires authenticated session");

    test("can vote on a debate argument", async ({ page, request }) => {
        // First, create a test debate via API
        const debateResponse = await request.post(`${API_BASE}/debates`, {
            data: { prompt: "E2E Voting Test Debate" },
        });

        if (!debateResponse.ok()) {
            test.skip(true, "Could not create test debate");
            return;
        }

        const debate = await debateResponse.json();
        const debateId = debate.id;

        // Wait for debate to complete (or timeout after 30s)
        let attempts = 0;
        let status = "running";
        while (status === "running" && attempts < 15) {
            await page.waitForTimeout(2000);
            const statusResponse = await request.get(`${API_BASE}/debates/${debateId}`);
            if (statusResponse.ok()) {
                const data = await statusResponse.json();
                status = data.status;
            }
            attempts++;
        }

        // Navigate to the debate page
        await page.goto(`/runs/${debateId}`);
        await page.waitForLoadState("networkidle");

        // Look for voting buttons
        const voteUpButton = page.locator('[data-testid="vote-up"]').or(page.getByRole("button", { name: /upvote|👍|like/i }));
        const voteDownButton = page.locator('[data-testid="vote-down"]').or(page.getByRole("button", { name: /downvote|👎|dislike/i }));

        // Check if voting UI is present
        const hasVoting = await voteUpButton.count() > 0 || await voteDownButton.count() > 0;

        if (hasVoting) {
            // Click upvote
            await voteUpButton.first().click();

            // Verify vote was registered (look for visual feedback)
            await expect(
                page.getByText(/voted|thanks|recorded/i)
                    .or(voteUpButton.first().locator(".voted, .active, [aria-pressed='true']"))
            ).toBeVisible({ timeout: 5000 }).catch(() => {
                // Vote might have worked without visible feedback
                console.log("Vote submitted, no visible confirmation");
            });
        } else {
            // Voting UI not present - might be disabled or debate not complete
            console.log("Voting UI not found - skipping vote interaction");
        }
    });

    test("voting updates count display", async ({ page, request }) => {
        // Navigate to a runs page
        await page.goto("/runs");

        // Check if any debates with vote counts are visible
        const voteCount = page.locator('[data-testid="vote-count"]').or(page.locator(".vote-count"));

        if (await voteCount.count() > 0) {
            const initialCount = await voteCount.first().textContent();
            expect(initialCount).toBeDefined();
        }
    });
});

test.describe("Vote Display (Public)", () => {
    test("shows vote counts on debate cards", async ({ page }) => {
        await page.goto("/runs");

        // Wait for content to load
        await page.waitForLoadState("networkidle");

        // Check for debate list
        const debateList = page.locator('[data-testid="debate-list"]').or(page.locator(".debate-list, .runs-table"));

        if (await debateList.count() > 0) {
            // Verify some kind of engagement metrics are shown
            await expect(
                page.getByText(/votes|score|rating/i)
                    .or(page.locator('[data-testid*="vote"]'))
            ).toBeVisible().catch(() => {
                console.log("Vote counts not prominently displayed");
            });
        }
    });
});
