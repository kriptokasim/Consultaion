"use client"

import { describe, it, expect } from "vitest"
import React from "react"
import { render, screen } from "@testing-library/react"
import { FeatureGate } from "../../components/FeatureGate"

describe("FeatureGate", () => {
  it("renders children when flag is enabled", () => {
    render(
      <FeatureGate flag="unifiedWorkspace" fallback={<div>Fallback</div>}>
        <div>Feature Content</div>
      </FeatureGate>
    )
    const body = document.body.textContent || ""
    expect(body).toContain("Feature Content")
  })

  it("renders fallback when flag is disabled", () => {
    render(
      <FeatureGate flag="unifiedWorkspace" fallback={<div>Fallback Content</div>}>
        <div>Feature Content</div>
      </FeatureGate>
    )
    const body = document.body.textContent || ""
    expect(body).toContain("Feature Content")
  })
})
