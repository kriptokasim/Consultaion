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
      "settings.nav.providerKeys": "API Keys",
      "settings.nav.profile": "Profile",
      "nav.mobile.label": "Primary navigation",
    })[key] ?? key,
  }),
}))

import { MobileBottomNav } from "./MobileBottomNav"

describe("MobileBottomNav", () => {
  it("uses localized labels and links Profile to settings", () => {
    render(<MobileBottomNav />)

    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Profile/ })).toHaveAttribute("href", "/settings/profile")
    expect(screen.getByRole("link", { name: /API Keys/ })).toHaveAttribute(
      "href",
      "/settings/provider-keys",
    )
  })
})
