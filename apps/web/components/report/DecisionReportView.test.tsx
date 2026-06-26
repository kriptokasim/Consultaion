import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { DecisionReportView, exportToMarkdown } from "./DecisionReportView";

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
    expect(screen.getAllByText("Proceed")[0]).toBeInTheDocument();
    expect(screen.getByText("Proceed with the project")).toBeInTheDocument();
  });

  it("renders confidence percentage", () => {
    render(<DecisionReportView report={mockReport} />);
    expect(screen.getAllByText("85%")[0]).toBeInTheDocument();
  });

  it("renders key findings", () => {
    render(<DecisionReportView report={mockReport} />);
    expect(screen.getByText("Security is adequate")).toBeInTheDocument();
    expect(screen.getByText("Cost concern")).toBeInTheDocument();
  });

  it("renders model positions", () => {
    render(<DecisionReportView report={mockReport} />);
    expect(screen.getAllByText("GPT-4o")[0]).toBeInTheDocument();
    expect(screen.getAllByText("supportive")[0]).toBeInTheDocument();
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
    expect(screen.queryByText(/Active Contradictions \(/)).not.toBeInTheDocument();
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

  it("renders UnstructuredSynthesisCard when report is null and rawSynthesis is provided", () => {
    const rawSynthesis = "This is a clean raw synthesis text without JSON.";
    render(<DecisionReportView report={null} rawSynthesis={rawSynthesis} />);
    expect(screen.getByText("Unstructured Synthesis Output")).toBeInTheDocument();
    expect(screen.getByText("This is a clean raw synthesis text without JSON.")).toBeInTheDocument();
  });

  it("renders FallbackResponseCard when synthesisStatus is fallback", () => {
    render(
      <DecisionReportView
        report={null}
        synthesisStatus="fallback"
        fallbackModel="Fallback-Model"
        fallbackReason="Primary model failed"
        rawSynthesis="Raw model fallback response."
      />
    );
    expect(screen.getByText("Fallback Response — No Fabricated Confidence")).toBeInTheDocument();
    expect(screen.getByText("Primary model failed")).toBeInTheDocument();
    expect(screen.getByText(/Fallback-Model/)).toBeInTheDocument();
    expect(screen.getByText("Raw model fallback response.")).toBeInTheDocument();
  });

  it("exportToMarkdown uses *100 for confidence, not *105", () => {
    const report = {
      title: "Export Test",
      verdict: {
        recommendation: "Proceed",
        confidence: 0.85,
        decision_type: "proceed",
        rationale: "Strong evidence.",
      },
    };
    const md = exportToMarkdown(report);
    expect(md).toContain("**Confidence:** 85%");
    expect(md).not.toContain("**Confidence:** 89%");
  });

  it("exportToMarkdown handles edge confidence values correctly", () => {
    const report = {
      title: "Edge Cases",
      verdict: { confidence: 1.0, decision_type: "proceed" },
    };
    expect(exportToMarkdown(report)).toContain("**Confidence:** 100%");

    const report2 = {
      title: "Zero",
      verdict: { confidence: 0, decision_type: "mixed" },
    };
    expect(exportToMarkdown(report2)).toContain("**Confidence:** 0%");
  });

  it("exportToMarkdown uses distinct_contribution and blind_spot for new schema", () => {
    const report = {
      title: "New Schema",
      model_positions: [
        {
          model: "Claude-4",
          stance: "supportive",
          distinct_contribution: "Novel risk framework",
          blind_spot: "Misses regulatory context",
        },
      ],
    };
    const md = exportToMarkdown(report);
    expect(md).toContain("Novel risk framework");
    expect(md).toContain("Blind Spot / Limitation: Misses regulatory context");
  });

  it("exportToMarkdown falls back to strongest_point and concern for legacy schema", () => {
    const report = {
      title: "Legacy Schema",
      model_positions: [
        {
          model: "GPT-4o",
          stance: "neutral",
          strongest_point: "Great summary",
          concern: "Missing detail",
        },
      ],
    };
    const md = exportToMarkdown(report);
    expect(md).toContain("Great summary");
    expect(md).toContain("Blind Spot / Limitation: Missing detail");
  });

  it("exportToMarkdown prefers distinct_contribution over strongest_point when both exist", () => {
    const report = {
      title: "Both Fields",
      model_positions: [
        {
          model: "Gemini",
          stance: "supportive",
          distinct_contribution: "New insight",
          strongest_point: "Old insight",
        },
      ],
    };
    const md = exportToMarkdown(report);
    expect(md).toContain("New insight");
    expect(md).not.toContain("Old insight");
  });

  it("renders full arena report structure with all expected sections", () => {
    render(<DecisionReportView report={mockReport} variant="arena" />);
    expect(screen.getByText("Test Decision Report")).toBeInTheDocument();
    expect(screen.queryByText("Context Needed to Make This Report Specific")).not.toBeInTheDocument();
    expect(screen.getAllByText("Key Findings").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Security is adequate")).toBeInTheDocument();
    expect(screen.getByText("Cost concern")).toBeInTheDocument();
    expect(screen.getAllByText("GPT-4o").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Risks & Assumptions").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Budget overrun risk")).toBeInTheDocument();
    expect(screen.getAllByText("Next Actions").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Caveats").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Analysis based on provided data only.")).toBeInTheDocument();
    expect(screen.getByText("Export")).toBeInTheDocument();
  });

  it("renders arena report with context needed when present", () => {
    const reportWithContext = {
      ...mockReport,
      context_needed: ["MRR data", "User count"],
    };
    render(<DecisionReportView report={reportWithContext} variant="arena" />);
    expect(screen.getByText("Context Needed to Make This Report Specific")).toBeInTheDocument();
    expect(screen.getByText("MRR data")).toBeInTheDocument();
  });

  it("renders parliament variant with 'Parliamentary Verification Passed' when verified", () => {
    const verifiedReport = {
      ...mockReport,
      quality_meta: {
        verification_status: "verified",
        completeness_score: 0.9,
        faithfulness_score: 0.9,
      },
    };
    render(<DecisionReportView report={verifiedReport} variant="parliament" />);
    expect(screen.getByText("Parliamentary Verification Passed")).toBeInTheDocument();
    expect(screen.queryByText("Verified & Faithful")).not.toBeInTheDocument();
  });

  it("shows parliament fallback message when synthesisStatus is fallback with variant=parliament", () => {
    render(
      <DecisionReportView
        report={null}
        variant="parliament"
        synthesisStatus="fallback"
        fallbackModel="Fallback-Model"
        fallbackReason="Primary model failed"
        rawSynthesis="Raw synthesis text."
      />
    );
    expect(screen.getByText("Fallback Response — No Fabricated Confidence")).toBeInTheDocument();
  });

  it("returns null when report is null and no rawSynthesis", () => {
    const { container } = render(<DecisionReportView report={null} />);
    expect(container.innerHTML).toBe("");
  });
});


