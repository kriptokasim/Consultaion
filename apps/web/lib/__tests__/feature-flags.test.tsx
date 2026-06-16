"use client"

import { describe, it, expect, vi } from "vitest"
import React from "react"
import { render } from "@testing-library/react"
import { FeatureGate } from "../../components/FeatureGate"
import * as featureFlagsModule from "../feature-flags"

vi.mock("../feature-flags", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../feature-flags")>()
  return {
    ...actual,
    isFeatureEnabled: vi.fn(),
  }
})

describe("FeatureGate", () => {
  it("renders children when flag is enabled", () => {
    vi.mocked(featureFlagsModule.isFeatureEnabled).mockReturnValue(true)

    render(
      <FeatureGate flag="unifiedWorkspace" fallback={<div>Fallback</div>}>
        <div>Feature Content</div>
      </FeatureGate>
    )
    const body = document.body.textContent || ""
    expect(body).toContain("Feature Content")
  })

  it("renders fallback when flag is disabled", () => {
    vi.mocked(featureFlagsModule.isFeatureEnabled).mockReturnValue(false)

    render(
      <FeatureGate flag="unifiedWorkspace" fallback={<div>Fallback Content</div>}>
        <div>Feature Content</div>
      </FeatureGate>
    )
    const body = document.body.textContent || ""
    expect(body).toContain("Fallback Content")
    expect(body).not.toContain("Feature Content")
  })
})
