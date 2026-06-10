import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { DifferentiationSection } from "./DifferentiationSection";

vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        "landing.differentiation.title": "Why not just ask two models yourself?",
        "landing.differentiation.subtitle": "You could paste your question into ChatGPT and Claude separately.",
      };
      return translations[key] || key;
    },
  }),
}));

describe("DifferentiationSection", () => {
  it("renders the headline", () => {
    render(<DifferentiationSection />);
    expect(
      screen.getByText("Why not just ask two models yourself?")
    ).toBeInTheDocument();
  });

  it("renders comparison points", () => {
    render(<DifferentiationSection />);
    expect(screen.getByText("Structured parallel comparison")).toBeInTheDocument();
    expect(screen.getByText("Disagreement surfaced automatically")).toBeInTheDocument();
    expect(screen.getByText("Structured decision report")).toBeInTheDocument();
  });

  it("does not contain fake benchmarks", () => {
    render(<DifferentiationSection />);
    expect(screen.queryByText(/10x faster/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/99%/i)).not.toBeInTheDocument();
  });
});
