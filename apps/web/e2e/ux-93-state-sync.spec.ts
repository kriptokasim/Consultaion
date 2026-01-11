import { test, expect } from '@playwright/test';

test.describe('Run Detail State Synchronization (UX-93)', () => {
    test('should show correct status and pending messages while running', async ({ page }) => {
        // 1. Mock a running debate
        await page.route('*/**/api/debates/ux-93-test', async (route) => {
            await route.fulfill({
                json: {
                    id: 'ux-93-test',
                    prompt: 'Test Debate',
                    status: 'running',
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                    panel_config: { seats: [] },
                    participant_errors: [],
                }
            });
        });

        // 2. Mock timeline (empty initially)
        await page.route('*/**/api/debates/ux-93-test/timeline', async (route) => {
            await route.fulfill({ json: [] });
        });

        // 3. Mock stream (simulate connecting...)
        await page.route('*/**/api/debates/ux-93-test/stream', async (route) => {
            // Keep connection open or close immediately, doesn't matter for initial render check
            // For this test we just want to see the UI state before events arrive.
            await new Promise(r => setTimeout(r, 100)); // slight delay
            await route.fulfill({ body: ': ok\n\n' });
        });

        // 4. Navigate
        await page.goto('/runs/ux-93-test');

        // 5. Verify Status Pill
        // Should NOT be "SUCCESS" (Emerald). Should be "RUNNING" (Blue/Default).
        // Debug what is visible
        const pills = page.locator('span.rounded-full');
        console.log("Pills:", await pills.allTextContents());

        // And ensure SUCCESS is NOT visible
        await expect(page.getByText('SUCCESS', { exact: true })).not.toBeVisible();

        // 6. Verify Empty State Messages
        // "Debate is running..." instead of "No messages recorded"
        await expect(page.getByText('Debate is running in the background')).toBeVisible();
        await expect(page.getByText('Final synthesis is being prepared')).toBeVisible();
        await expect(page.getByText('No synthesized final answer was recorded')).not.toBeVisible();
    });

    test('should show Round 1 correctly in Replay', async ({ page }) => {
        // 1. Mock completed debate with events
        await page.route('*/**/api/debates/ux-93-replay', async (route) => {
            await route.fulfill({
                json: {
                    id: 'ux-93-replay',
                    prompt: 'Replay Test',
                    status: 'completed',
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                }
            });
        });

        await page.route('*/**/api/debates/ux-93-replay/timeline', async (route) => {
            await route.fulfill({
                json: [
                    { type: 'system_notice', content: 'Init', ts: new Date().toISOString() },
                    { type: 'round_start', round_index: 1, content: 'Round 1 started', ts: new Date().toISOString() },
                    { type: 'message', round_index: 1, role: 'agent', content: 'Hello', ts: new Date().toISOString() }
                ]
            });
        });

        await page.goto('/runs/ux-93-replay');

        // Navigate to Replay tab if it exists, or scroll to Replay component
        // Assuming Replay component is visible or we assume Replay logic is tested via component visibility
        // The Replay component is rendered on the page in `RunDetailClient`? 
        // Actually `RunDetailClient` renders `DebateArena` and `ParliamentRunView`. `DebateReplay` is likely inside `DebateArena` or separate page.
        // Checking file structure: `app/(app)/runs/[id]/replay/ReplayPageClient.tsx` exists.
        // So Replay is likely a sub-route or a separate view.

        // Let's check `RunDetailClient` again. It renders `ParliamentRunView` and `DebateArena`.
        // `DebateArena` might contain the visualizer.
        // But the screenshot showed "Replay" typically on a separate page or modal?
        // Wait, `DebateReplay` component was edited. Where is it used?

        // If `DebateReplay` is used in `/runs/[id]/replay`, we should go there.
        await page.goto('/runs/ux-93-replay/replay'); // Guessing route based on file structure

        // Verify Round 1
        await expect(page.getByText('Round 1', { exact: false })).toBeVisible();
        await expect(page.getByText('Round 2', { exact: false })).not.toBeVisible();
    });
});
