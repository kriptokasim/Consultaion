import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  setTheme: vi.fn(),
}))

vi.mock("next-themes", () => ({
  useTheme: () => ({
    resolvedTheme: "dark",
    setTheme: mocks.setTheme,
  }),
}))

vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

import { AuthShell } from "./AuthShell"

describe("AuthShell", () => {
  beforeEach(() => {
    mocks.setTheme.mockReset()
  })

  it("uses the shared next-themes state", () => {
    render(
      <AuthShell title="Sign in">
        <div>Form</div>
      </AuthShell>,
    )

    fireEvent.click(screen.getByRole("button", { name: "auth.theme.toggle" }))

    expect(mocks.setTheme).toHaveBeenCalledWith("light")
  })
})
