import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  login: vi.fn(),
  push: vi.fn(),
  searchParams: new URLSearchParams(),
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
  useSearchParams: () => mocks.searchParams,
}))

vi.mock("@/lib/auth", () => ({
  login: mocks.login,
}))

vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock("@/components/auth/AuthShell", () => ({
  AuthShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/components/auth/GoogleButton", () => ({
  default: () => null,
}))

import LoginClient from "./LoginClient"

async function submitLogin() {
  fireEvent.change(screen.getByLabelText("auth.login.email"), {
    target: { value: "user@example.com" },
  })
  fireEvent.change(screen.getByLabelText("auth.login.password"), {
    target: { value: "password" },
  })
  fireEvent.click(screen.getByRole("button", { name: "auth.login.cta" }))
  await waitFor(() => expect(mocks.login).toHaveBeenCalled())
}

describe("LoginClient next redirect", () => {
  beforeEach(() => {
    mocks.login.mockReset()
    mocks.login.mockResolvedValue(undefined)
    mocks.push.mockReset()
    mocks.searchParams = new URLSearchParams()
  })

  it("preserves a valid internal destination", async () => {
    mocks.searchParams = new URLSearchParams("next=%2Fdashboard%3Ftab%3Dusage")
    render(<LoginClient />)

    await submitLogin()

    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/dashboard?tab=usage"))
  })

  it.each([
    "https://evil.example/phish",
    "//evil.example/phish",
    "javascript:alert(1)",
    "%2F%2Fevil.example%2Fphish",
  ])("falls back to /live for unsafe destination %s", async (nextPath) => {
    mocks.searchParams = new URLSearchParams()
    mocks.searchParams.set("next", nextPath)
    render(<LoginClient />)

    await submitLogin()

    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/live"))
  })
})
