import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { startDebate } from "./api";

describe("startDebate idempotency", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockImplementation(
      async () =>
        new Response(JSON.stringify({ id: "d1", status: "queued" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("sends the idempotency key so a retried start reuses the first run", async () => {
    await startDebate({ prompt: "p", mode: "arena" }, "run-key-123456");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(init.headers).get("X-Idempotency-Key")).toBe("run-key-123456");
  });

  it("omits the header when no key is given", async () => {
    await startDebate({ prompt: "p", mode: "arena" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(init.headers).has("X-Idempotency-Key")).toBe(false);
  });
});
