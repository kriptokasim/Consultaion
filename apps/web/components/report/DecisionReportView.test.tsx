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

  it("renders unverified when verification_error is true (critic failure)", () => {
    const criticFailReport = {
      ...mockReport,
      quality_meta: {
        verification_status: "unverified",
        verification_error: true,
        verification_source: "unavailable",
        completeness_score: null,
        faithfulness_score: null,
        critic_feedback: "Verifier service temporarily unavailable.",
      },
    };
    render(<DecisionReportView report={criticFailReport} />);
    expect(screen.getByText("Unverified")).toBeInTheDocument();
    expect(screen.getByText("Verifier service temporarily unavailable.")).toBeInTheDocument();
    // Should show "Unavailable" for scores, not fake percentages
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });

  it("does not show verified when verification_error is true", () => {
    const errorReport = {
      ...mockReport,
      quality_meta: {
        verification_status: "unverified",
        verification_error: true,
        verification_source: "unavailable",
        completeness_score: null,
        faithfulness_score: null,
      },
    };
    render(<DecisionReportView report={errorReport} />);
    expect(screen.queryByText("Verified & Faithful")).not.toBeInTheDocument();
  });

  it("renders unique insights label instead of contested & unique stances", () => {
    const reportWithDivergence = {
      ...mockReport,
      divergence_breakdown: {
        divergence_score: 0.3,
        consensus_claims: [{ claim: "Kafka scales well", models: ["M1", "M2"] }],
        unique_insights: [{ claim: "Redis is better for low latency", model: "M2" }],
        contested_claims: [{ claim: "Redis is better for low latency", model: "M2" }],
        contradiction_details: [],
      },
    };
    render(<DecisionReportView report={reportWithDivergence} />);
    expect(screen.getByText(/Unique \/ Single-Model Insights/)).toBeInTheDocument();
    expect(screen.queryByText(/Contested & Unique Stances/)).not.toBeInTheDocument();
  });

  it("hides active contradictions when empty", () => {
    const reportNoContradictions = {
      ...mockReport,
      divergence_breakdown: {
        divergence_score: 0.1,
        consensus_claims: [],
        unique_insights: [{ claim: "Some unique claim", model: "M1" }],
        contradiction_details: [],
        active_contradictions: [],
      },
    };
    render(<DecisionReportView report={reportNoContradictions} />);
    expect(screen.queryByText(/Active Contradictions/)).not.toBeInTheDocument();
  });

  it("shows context needed section when present", () => {
    const reportWithContext = {
      ...mockReport,
      context_needed: ["Current MRR/ARR", "Number of active users", "ICP definition"],
    };
    render(<DecisionReportView report={reportWithContext} />);
    expect(screen.getByText("Context Needed to Make This Report Specific")).toBeInTheDocument();
    expect(screen.getByText("Current MRR/ARR")).toBeInTheDocument();
    expect(screen.getByText("ICP definition")).toBeInTheDocument();
  });

  it("does not render context needed section when empty", () => {
    const reportNoContext = {
      ...mockReport,
      context_needed: [],
    };
    render(<DecisionReportView report={reportNoContext} />);
    expect(screen.queryByText("Context Needed to Make This Report Specific")).not.toBeInTheDocument();
  });

  it("renders ReportGenerationFailedCard when report contains raw JSON", () => {
    const corruptReport = {
      ...mockReport,
      executive_summary: "```json\n{\n  \"verdict\": \"leak\"\n}\n```",
    };
    render(<DecisionReportView report={corruptReport} />);
    expect(screen.getByText("Decision Report Validation Guard Triggered")).toBeInTheDocument();
  });

  it("renders ReportGenerationFailedCard when report has renderable false in quality_meta", () => {
    const unrenderableReport = {
      ...mockReport,
      quality_meta: {
        renderable: false,
        critic_feedback: "Failed integrity check due to JSON leak",
      },
    };
    render(<DecisionReportView report={unrenderableReport} />);
    expect(screen.getByText("Decision Report Validation Guard Triggered")).toBeInTheDocument();
    expect(screen.getByText("Failed integrity check due to JSON leak")).toBeInTheDocument();
  });

  it("renders ReportGenerationFailedCard when report is null but rawSynthesis contains a raw JSON block", () => {
    const rawSynthesis = "```json\n{\n  \"verdict\": \"leak\"\n}\n```";
    render(<DecisionReportView report={null} rawSynthesis={rawSynthesis} />);
    expect(screen.getByText("Decision Report Validation Guard Triggered")).toBeInTheDocument();
  });
});
