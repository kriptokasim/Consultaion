import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/settings/provider-keys",
}));

import { I18nClientProvider } from "@/lib/i18n/I18nClientProvider";
import { getDictionary } from "@/lib/i18n/dictionaries";

import { PrimaryNav } from "./PrimaryNav";

function renderNav(variant?: "inline" | "bottom-bar") {
  return render(
    <I18nClientProvider locale="en" messages={getDictionary("en")}>
      <PrimaryNav variant={variant} />
    </I18nClientProvider>,
  );
}

describe("PrimaryNav", () => {
  it("renders the four canonical destinations", () => {
    renderNav();
    expect(screen.getByRole("link", { name: "Runs" })).toHaveAttribute("href", "/runs");
    expect(screen.getByRole("link", { name: "Ask" })).toHaveAttribute("href", "/new");
    expect(screen.getByRole("link", { name: "Panel" })).toHaveAttribute("href", "/settings/provider-keys");
    expect(screen.getByRole("link", { name: "You" })).toHaveAttribute("href", "/settings");
  });

  it("marks only the longest-prefix match as the current page", () => {
    renderNav();
    expect(screen.getByRole("link", { name: "Panel" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "You" })).not.toHaveAttribute("aria-current");
  });

  it("exposes an accessible navigation landmark", () => {
    renderNav();
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument();
  });
});
