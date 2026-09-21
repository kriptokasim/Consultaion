import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { DecisionReport } from "./DecisionReport";

const mockReport = {
  title: "Test Decision Report",
  executive_summary: "This is a summary of the analysis.",
  verdict: {
    recommendation: "Proceed with the project",
    confidence: 0.85,
    decision_type: "proceed",
    rationale: "The analysis strongly supports this decision.",
  },
  key_findings: [{ title: "Security is adequate", summary: "All checks passed.", importance: "high" }],
  model_positions: [
    { model: "GPT-4o", stance: "supportive", strongest_point: "Strong ROI case", concern: "Timeline tight" },
  ],
  risks_and_assumptions: [{ item: "Budget overrun risk", type: "risk", severity: "high" }],
  next_actions: [{ action: "Approve budget", priority: "now" }],
  caveats: ["Analysis based on provided data only."],
};

describe("DecisionReport", () => {
  it("audience=record renders every section, matching the pre-PS06 default", () => {
    render(<DecisionReport run={{ report: mockReport }} audience="record" />);
    expect(screen.getByText("Test Decision Report")).toBeInTheDocument();
    expect(screen.getByText("Security is adequate")).toBeInTheDocument();
    expect(screen.getAllByText("GPT-4o").length).toBeGreaterThan(0);
    expect(screen.getByText("Budget overrun risk")).toBeInTheDocument();
    expect(screen.getByText("Approve budget")).toBeInTheDocument();
    expect(screen.getByText("Focus Mode")).toBeInTheDocument(); // showChrome=true for record
  });

  it("audience=brief condenses to verdict/findings/actions/caveats and hides record-depth detail", () => {
    render(<DecisionReport run={{ report: mockReport }} audience="brief" />);
    expect(screen.getByText("Test Decision Report")).toBeInTheDocument();
    expect(screen.getByText("Security is adequate")).toBeInTheDocument();
    expect(screen.getByText("Approve budget")).toBeInTheDocument();
    expect(screen.getByText("Analysis based on provided data only.")).toBeInTheDocument();

    expect(screen.queryByText("Model Positions")).not.toBeInTheDocument();
    expect(screen.queryByText("GPT-4o")).not.toBeInTheDocument();
    expect(screen.queryByText("Risks & Assumptions")).not.toBeInTheDocument();
    expect(screen.queryByText("Budget overrun risk")).not.toBeInTheDocument();
    expect(screen.queryByText("Focus Mode")).not.toBeInTheDocument(); // showChrome=false for brief
  });

  it("never hides failure/fallback states for a brief audience", () => {
    render(
      <DecisionReport
        run={{ report: null, synthesisStatus: "fallback", fallbackModel: "Fallback-Model", fallbackReason: "Primary model failed", rawSynthesis: "Raw response." }}
        audience="brief"
      />,
    );
    expect(screen.getByText("Fallback Response — No Fabricated Confidence")).toBeInTheDocument();
    expect(screen.getByText("Primary model failed")).toBeInTheDocument();
  });

  it("applies the paper-surface class regardless of audience", () => {
    const { container: recordContainer } = render(<DecisionReport run={{ report: mockReport }} audience="record" />);
    const { container: briefContainer } = render(<DecisionReport run={{ report: mockReport }} audience="brief" />);
    expect(recordContainer.querySelector(".new-ux-report-paper")).toBeInTheDocument();
    expect(briefContainer.querySelector(".new-ux-report-paper")).toBeInTheDocument();
  });
});
