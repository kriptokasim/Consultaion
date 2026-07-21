import { describe, expect, it } from "vitest";

import { resolveServerApiOrigin } from "./apiOrigin";

describe("resolveServerApiOrigin", () => {
  it("prefers the container-internal API origin", () => {
    expect(
      resolveServerApiOrigin({
        API_INTERNAL_URL: "http://api:8000",
        NEXT_PUBLIC_API_URL: "https://api.example.com",
      }),
    ).toBe("http://api:8000");
  });

  it("falls back to the public API origin outside container deployments", () => {
    expect(
      resolveServerApiOrigin({
        NEXT_PUBLIC_API_URL: "https://api.example.com",
      }),
    ).toBe("https://api.example.com");
  });

  it("uses localhost only when neither API origin is configured", () => {
    expect(resolveServerApiOrigin({})).toBe("http://localhost:8000");
  });
});
