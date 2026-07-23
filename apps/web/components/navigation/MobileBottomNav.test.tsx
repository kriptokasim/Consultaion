import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({
  usePathname: () => "/settings",
}))

vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({
    t: (key: string) => ({
      "nav.arena": "Arena",
      "nav.runs": "Runs",
      "nav.mobile.arena": "Arena",
      "nav.mobile.runs": "Runs",
      "nav.mobile.providerKeys": "Keys",
      "nav.mobile.profile": "Profile",
      "settings.nav.providerKeys": "API Keys",
      "settings.nav.profile": "Profile",
      "nav.mobile.label": "Primary navigation",
    })[key] ?? key,
  }),
}))

import { MobileBottomNav } from "./MobileBottomNav"

describe("MobileBottomNav", () => {
  it("uses concise localized labels without losing accessible names", () => {
    render(<MobileBottomNav />)

    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toHaveClass(
      "h-[calc(var(--mobile-bottom-nav-height)+env(safe-area-inset-bottom))]",
    )
    expect(screen.getByRole("link", { name: /Profile/ })).toHaveAttribute("href", "/settings/profile")
    expect(screen.getByRole("link", { name: /API Keys/ })).toHaveAttribute(
      "href",
      "/settings/provider-keys",
    )
    expect(screen.getByText("Keys")).toHaveClass("truncate", "whitespace-nowrap")
  })
})
