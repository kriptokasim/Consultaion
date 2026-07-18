import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchWithAuth } from "./auth";

describe("fetchWithAuth CSRF protection", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    document.cookie = "csrf_token=csrf%20value; path=/";
  });

  afterEach(() => {
    document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("adds the double-submit token to unsafe requests", async () => {
    await fetchWithAuth("/debates/d1/share", { method: "POST" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("csrf value");
  });

  it("preserves an explicitly supplied CSRF token", async () => {
    await fetchWithAuth("/debates/d1/share", {
      method: "POST",
      headers: { "X-CSRF-Token": "explicit" },
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("explicit");
  });

  it("does not add a CSRF header to safe requests", async () => {
    await fetchWithAuth("/debates/d1");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(init.headers).has("X-CSRF-Token")).toBe(false);
  });

  it("does not duplicate an existing API prefix", async () => {
    await fetchWithAuth("/api/provider-keys", { method: "POST" });

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/provider-keys");
  });
});
