"use client"

import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { FallbackResponseCard } from "./FallbackResponseCard"

describe("FallbackResponseCard", () => {
  it("renders the content without fabricated confidence", () => {
    render(
      <FallbackResponseCard
        model="gpt-4"
        content="This is the fallback response content."
      />
    )

    expect(screen.getByText("This is the fallback response content.")).toBeInTheDocument()
    expect(screen.getByText("gpt-4")).toBeInTheDocument()
    expect(screen.queryByText("Confidence")).not.toBeInTheDocument()
  })

  it("shows reason when provided", () => {
    render(
      <FallbackResponseCard
        reason="Synthesis validation failed"
        content="Fallback output"
      />
    )

    expect(screen.getByText("Synthesis validation failed")).toBeInTheDocument()
    expect(screen.getByText("Fallback output")).toBeInTheDocument()
  })

  it("renders default reason when not provided", () => {
    render(<FallbackResponseCard content="test" />)

    expect(screen.getByText(/Synthesis failed/)).toBeInTheDocument()
  })

  it("applies custom className", () => {
    const { container } = render(
      <FallbackResponseCard content="test" className="my-custom-class" />
    )

    expect(container.firstElementChild).toHaveClass("my-custom-class")
  })
})
