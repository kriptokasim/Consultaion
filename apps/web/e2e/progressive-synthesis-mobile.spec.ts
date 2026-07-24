import { expect, test, type Page } from "@playwright/test";

const debateId = "progressive-mobile-contract";

const persistedResponse = {
  id: "message-a",
  response_id: "response-a",
  debate_id: debateId,
  response_type: "arena_response",
  role: "arena_response",
  round: 1,
  model_id: "model-a",
  display_name: "Model A",
  provider: "test",
  content: "The fast model answer stays visible beside the decision.",
  success: true,
  error_code: null,
  error_message: null,
  retryable: false,
  created_at: new Date().toISOString(),
  metadata: {
    logo_url: null,
    persona_type: null,
    persona_tagline: null,
    run_attempt: 2,
    retry_generation: 0,
  },
};

const synthesisBase = {
  contract_version: 1,
  debate_id: debateId,
  synthesis_id: `synth-${debateId}-a2-r0`,
  run_attempt: 2,
  revision: 0,
  status: "provisional",
  input_hash: "snapshot-a",
  response_ids: ["response-a"],
  successful_count: 1,
  total_count: 2,
};

async function installEventSourceFixture(page: Page) {
  await page.addInitScript(({ base }) => {
    class FixtureEventSource {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSED = 2;
      readonly CONNECTING = 0;
      readonly OPEN = 1;
      readonly CLOSED = 2;
      readonly url: string;
      readonly withCredentials = true;
      readyState = FixtureEventSource.CONNECTING;
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      private timers: number[] = [];

      constructor(url: string | URL) {
        this.url = String(url);
        this.schedule(15, () => {
          this.readyState = FixtureEventSource.OPEN;
          this.onopen?.(new Event("open"));
        });
        this.emit(60, {
          type: "arena_synthesis_started",
          ...base,
        }, "1");
        this.emit(120, {
          type: "arena_synthesis_delta",
          ...base,
          response_id: base.synthesis_id,
          model_id: "synthesizer",
          text: "Fast provisional decision",
          delta_sequence: 1,
          accumulated_chars: 25,
        }, "2");
        this.emit(220, {
          type: "arena_synthesis_revision",
          ...base,
          content: "Fast provisional decision",
          report: null,
        }, "3");
        this.emit(2_500, {
          type: "arena_synthesis_finalized",
          ...base,
          synthesis_id: `synth-${base.debate_id}-a2`,
          revision: 1,
          status: "final",
          input_hash: "snapshot-ab",
          response_ids: ["response-a", "response-b"],
          successful_count: 2,
          content: "Converged final decision",
          report: null,
          provisional_promoted: false,
        }, "4");
      }

      addEventListener() {}
      removeEventListener() {}
      dispatchEvent() { return true; }

      close() {
        this.readyState = FixtureEventSource.CLOSED;
        this.timers.forEach((timer) => window.clearTimeout(timer));
        this.timers = [];
      }

      private schedule(delay: number, callback: () => void) {
        this.timers.push(window.setTimeout(callback, delay));
      }

      private emit(delay: number, data: unknown, lastEventId: string) {
        this.schedule(delay, () => {
          if (this.readyState === FixtureEventSource.CLOSED) return;
          this.onmessage?.(new MessageEvent("message", {
            data: JSON.stringify(data),
            lastEventId,
          }));
        });
      }
    }

    Object.defineProperty(window, "EventSource", {
      configurable: true,
      value: FixtureEventSource,
    });
  }, { base: synthesisBase });
}

async function mockRunBoundaries(page: Page) {
  await page.route(new RegExp(`/debates/${debateId}/responses(?:\\?.*)?$`), (route) => route.fulfill({
    json: {
      contract_version: 1,
      items: [persistedResponse],
      summary: {
        expected: 2,
        persisted: 1,
        successful: 1,
        failed: 0,
      },
    },
  }));
  await page.route(new RegExp(`/debates/${debateId}/timeline(?:\\?.*)?$`), (route) => route.fulfill({
    json: { items: [] },
  }));
  await page.route(new RegExp(`/debates/${debateId}/events(?:\\?.*)?$`), (route) => route.fulfill({
    json: { items: [] },
  }));
  await page.route(new RegExp(`/debates/${debateId}(?:\\?.*)?$`), (route) => route.fulfill({
    json: {
      id: debateId,
      prompt: "Should we ship the realtime synthesis?",
      mode: "arena",
      status: "running",
      run_attempt: 2,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      config: { locale: "en" },
      panel_config: {
        seats: [
          { model_id: "model-a", model: "model-a" },
          { model_id: "model-b", model: "model-b" },
        ],
      },
      models: [
        { model_id: "model-a", display_name: "Model A", provider: "test" },
        { model_id: "model-b", display_name: "Model B", provider: "test" },
      ],
    },
  }));
  await page.route(/\/me(?:\?.*)?$/, (route) => route.fulfill({
    json: { id: "user-1", email: "mobile@example.com" },
  }));
}

for (const viewport of [
  { name: "320", width: 320, height: 700 },
  { name: "360", width: 360, height: 780 },
  { name: "390", width: 390, height: 844 },
  { name: "430", width: 430, height: 900 },
  { name: "landscape", width: 844, height: 390 },
]) {
  test(`progressive synthesis remains usable at ${viewport.name}px`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await installEventSourceFixture(page);
    await mockRunBoundaries(page);

    await page.goto(`/live?run=${debateId}`);

    const sourceAnswer = page.locator("p:visible").filter({
      hasText: "The fast model answer stays visible beside the decision.",
    });
    await expect(sourceAnswer).toHaveCount(1);

    const decisionTab = page.getByRole("tab", { name: /Decision|Karar/ });
    if (await decisionTab.isVisible()) {
      const box = await decisionTab.boundingBox();
      expect(box?.height).toBeGreaterThanOrEqual(44);
      await decisionTab.click();
    }

    const card = page.getByTestId("live-synthesis-card");
    await expect(card).toContainText("Fast provisional decision");
    await expect(card).toContainText(/Draft|Taslak/);
    await expect(card).toContainText("Converged final decision");
    await expect(card).toContainText(/Final/);

    const noHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    );
    expect(noHorizontalOverflow).toBe(true);
    await expect(page.locator("[data-nextjs-dialog]")).toHaveCount(0);
  });
}
