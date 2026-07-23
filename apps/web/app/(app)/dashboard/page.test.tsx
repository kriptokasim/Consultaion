import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  getMe: vi.fn(),
  redirect: vi.fn(),
}))

vi.mock("@/lib/auth", () => ({
  getMe: mocks.getMe,
}))

vi.mock("next/navigation", () => ({
  redirect: mocks.redirect,
}))

vi.mock("./DashboardClient", () => ({
  default: () => null,
}))

import DashboardPage from "./page"

describe("DashboardPage", () => {
  beforeEach(() => {
    mocks.getMe.mockReset()
    mocks.redirect.mockReset()
  })

  it("preserves /dashboard as the post-login destination", async () => {
    mocks.getMe.mockResolvedValue(null)
    mocks.redirect.mockImplementation(() => {
      throw new Error("NEXT_REDIRECT")
    })

    await expect(DashboardPage()).rejects.toThrow("NEXT_REDIRECT")
    expect(mocks.redirect).toHaveBeenCalledWith("/login?next=/dashboard")
  })
})
