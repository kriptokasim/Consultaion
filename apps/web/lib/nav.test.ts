import { describe, expect, it } from "vitest";

import { isNavItemActive, PRIMARY_NAV_ITEMS } from "./nav";

const [runs, ask, panel, you] = PRIMARY_NAV_ITEMS;

describe("isNavItemActive", () => {
  it("matches the exact route", () => {
    expect(isNavItemActive("/runs", runs)).toBe(true);
    expect(isNavItemActive("/new", ask)).toBe(true);
  });

  it("matches a sub-route of its own href", () => {
    expect(isNavItemActive("/runs/abc-123", runs)).toBe(true);
  });

  it("does not match an unrelated route", () => {
    expect(isNavItemActive("/settings", runs)).toBe(false);
  });

  it("resolves nested-prefix conflicts to the longest match only", () => {
    // /settings/provider-keys is a prefix match for "you" (/settings) too,
    // but "panel" (/settings/provider-keys) is the more specific match.
    expect(isNavItemActive("/settings/provider-keys", panel)).toBe(true);
    expect(isNavItemActive("/settings/provider-keys", you)).toBe(false);
  });

  it("still matches the shorter route on its own", () => {
    expect(isNavItemActive("/settings", you)).toBe(true);
    expect(isNavItemActive("/settings/profile", you)).toBe(true);
  });
});
