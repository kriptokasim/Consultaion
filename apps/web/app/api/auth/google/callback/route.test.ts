import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

describe("Google OAuth callback API origin", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("exchanges the code through the container-internal API origin", async () => {
    vi.stubEnv("API_INTERNAL_URL", "http://api:8000");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: vi.fn().mockResolvedValue({ code: "exchange_rejected" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { GET } = await import("./route");
    const request = new NextRequest(
      "https://web.consultaion.com/api/auth/google/callback?code=oauth-code&state=oauth-state",
      { headers: { cookie: "oauth_state=oauth-state" } },
    );

    await GET(request);

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://api:8000/auth/google/callback",
    );
  });
});
