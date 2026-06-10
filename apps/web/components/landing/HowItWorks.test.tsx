import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { HowItWorks } from "./HowItWorks";

vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        "landing.howItWorks.title": "How Consultaion turns debate into a decision",
        "landing.howItWorks.subtitle": "From question to decision report",
        "landing.howItWorks.steps.ask.title": "Ask one decision question",
        "landing.howItWorks.steps.ask.description": "Start with one strategic question.",
        "landing.howItWorks.steps.compare.title": "Compare model perspectives",
        "landing.howItWorks.steps.compare.description": "Multiple AI models respond.",
        "landing.howItWorks.steps.divergence.title": "Surface disagreement",
        "landing.howItWorks.steps.divergence.description": "Identifies consensus.",
        "landing.howItWorks.steps.report.title": "Receive a decision report",
        "landing.howItWorks.steps.report.description": "Structured report.",
      };
      return translations[key] || key;
    },
  }),
}));

describe("HowItWorks", () => {
  it("renders section title", () => {
    render(<HowItWorks />);
    expect(
      screen.getByText("How Consultaion turns debate into a decision")
    ).toBeInTheDocument();
  });

  it("contains four steps", () => {
    render(<HowItWorks />);
    expect(screen.getAllByText("Ask one decision question").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Compare model perspectives").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Surface disagreement").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Receive a decision report").length).toBeGreaterThanOrEqual(1);
  });
});
