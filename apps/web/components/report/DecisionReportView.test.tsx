import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { DecisionReportView } from "./DecisionReportView";

describe("DecisionReportView", () => {
  const mockReport = {
    title: "Test Decision Report",
    executive_summary: "This is a summary of the analysis.",
    verdict: {
      recommendation: "Proceed with the project",
      confidence: 0.85,
      decision_type: "proceed",
      rationale: "The analysis strongly supports this decision.",
    },
    key_findings: [
      { title: "Security is adequate", summary: "All checks passed.", importance: "high" },
      { title: "Cost concern", summary: "Budget may be tight.", importance: "medium" },
    ],
    model_positions: [
      { model: "GPT-4o", stance: "supportive", strongest_point: "Strong ROI case", concern: "Timeline tight" },
    ],
    risks_and_assumptions: [
      { item: "Budget overrun risk", type: "risk", severity: "high" },
    ],
    next_actions: [
      { action: "Approve budget", priority: "now" },
      { action: "Schedule review", priority: "next" },
    ],
    caveats: ["Analysis based on provided data only."],
  };

  it("renders the report title", () => {
    render(<DecisionReportView report={mockReport} />);
    expect(screen.getByText("Test Decision Report")).toBeInTheDocument();
  });

  it("renders the verdict card", () => {
    render(<DecisionReportView report={mockReport} />);
    expect(screen.getByText("Proceed")).toBeInTheDocument();
    expect(screen.getByText("Proceed with the project")).toBeInTheDocument();
  });

  it("renders confidence percentage", () => {
    render(<DecisionReportView report={mockReport} />);
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("renders key findings", () => {
    render(<DecisionReportView report={mockReport} />);
    expect(screen.getByText("Security is adequate")).toBeInTheDocument();
    expect(screen.getByText("Cost concern")).toBeInTheDocument();
  });

  it("renders model positions", () => {
    render(<DecisionReportView report={mockReport} />);
    expect(screen.getByText("GPT-4o")).toBeInTheDocument();
    expect(screen.getByText("supportive")).toBeInTheDocument();
  });

  it("renders risks", () => {
    render(<DecisionReportView report={mockReport} />);
    expect(screen.getByText("Budget overrun risk")).toBeInTheDocument();
  });

  it("renders next actions", () => {
    render(<DecisionReportView report={mockReport} />);
    expect(screen.getByText("Approve budget")).toBeInTheDocument();
    expect(screen.getByText("Schedule review")).toBeInTheDocument();
  });

  it("renders caveats", () => {
    render(<DecisionReportView report={mockReport} />);
    expect(screen.getByText("Analysis based on provided data only.")).toBeInTheDocument();
  });

  it("returns null when report is null", () => {
    const { container } = render(<DecisionReportView report={null} />);
    expect(container.innerHTML).toBe("");
  });

  it("hides empty sections gracefully", () => {
    const minimalReport = {
      title: "Minimal",
      verdict: { recommendation: "Proceed", confidence: 0.5, decision_type: "proceed", rationale: "" },
    };
    render(<DecisionReportView report={minimalReport} />);
    expect(screen.getByText("Minimal")).toBeInTheDocument();
    // Key Findings section should not render
    expect(screen.queryByText("Key Findings")).not.toBeInTheDocument();
  });

  it("shows export button", () => {
    render(<DecisionReportView report={mockReport} />);
    expect(screen.getByText("Export")).toBeInTheDocument();
  });

  it("renders verified status when verification_status is verified or omitted", () => {
    const verifiedReport = {
      ...mockReport,
      quality_meta: {
        verification_status: "verified",
        completeness_score: 0.9,
        faithfulness_score: 0.9,
      },
    };
    render(<DecisionReportView report={verifiedReport} />);
    expect(screen.getByText("Verified & Faithful")).toBeInTheDocument();
  });

  it("renders unverified status when verification_status is unverified", () => {
    const unverifiedReport = {
      ...mockReport,
      quality_meta: {
        verification_status: "unverified",
        completeness_score: 0.9,
        faithfulness_score: 0.9,
      },
    };
    render(<DecisionReportView report={unverifiedReport} />);
    expect(screen.getByText("Unverified")).toBeInTheDocument();
  });

  it("renders verification failed status when verification_status is failed", () => {
    const failedReport = {
      ...mockReport,
      quality_meta: {
        verification_status: "failed",
        completeness_score: 0.9,
        faithfulness_score: 0.9,
      },
    };
    render(<DecisionReportView report={failedReport} />);
    expect(screen.getByText("Verification Failed")).toBeInTheDocument();
  });
});
