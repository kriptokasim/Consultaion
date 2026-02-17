import { test, expect } from '@playwright/test';

test.describe('Timeline Logic', () => {
    test('hydrates from REST and updates from SSE', async ({ page }) => {
        const debateId = 'timeline-test-id';

        // 1. Mock Debate Detail
        await page.route(`*/**/api/debates/${debateId}`, async (route) => {
            await route.fulfill({
                json: {
                    id: debateId,
                    topic: 'Test Topic',
                    status: 'running',
                    config: { topic: 'Test Topic' }
                }
            });
        });

        // 2. Mock Initial Timeline (Hydration)
        const initialEvents = [
            {
                id: 'evt-1',
                debate_id: debateId,
                type: 'notice',
                round: 0,
                ts: new Date().toISOString(),
                payload: { text: 'Debate started' }
            }
        ];
        await page.route(`*/**/api/debates/${debateId}/timeline`, async (route) => {
            await route.fulfill({ json: initialEvents });
        });

        // 3. Mock SSE Stream (Simplified)
        await page.route(`*/**/api/debates/${debateId}/stream`, async (route) => {
            const event = {
                id: 'evt-2',
                debate_id: debateId,
                type: 'message',
                round: 1,
                ts: new Date().toISOString(),
                payload: {
                    text: 'Live update message',
                    actor: 'Test Agent',
                    role: 'agent'
                }
            };
            await route.fulfill({
                status: 200,
                headers: { 'Content-Type': 'text/event-stream' },
                body: `data: ${JSON.stringify(event)}\n\n`
            });
        });


        // 4. Navigate
        await page.goto(`/runs/${debateId}`);

        // 5. Verify Initial Event
        await expect(page.getByText('Debate started')).toBeVisible();

        // 6. Verify Listen Event (might appear immediately with the mock above)
        await expect(page.getByText('Live update message')).toBeVisible();
        await expect(page.getByText('Test Agent')).toBeVisible();
    });
});
