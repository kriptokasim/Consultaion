import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { ParliamentReportSection } from "./ParliamentRunView";

describe("ParliamentReportSection", () => {
  it("does not render fabricated Debate Verdict report when synthesisReport is absent", () => {
    render(<ParliamentReportSection text="Some synthesis text without structured report." />);
    expect(screen.queryByText("Debate Verdict")).not.toBeInTheDocument();
    expect(screen.queryByText("65%")).not.toBeInTheDocument();
    expect(screen.queryByText("0.65")).not.toBeInTheDocument();
    expect(screen.getByText("Structured Parliamentary Report")).toBeInTheDocument();
    expect(screen.getByText(/Structured parliamentary report unavailable/)).toBeInTheDocument();
  });

  it("renders the unavailable note when text is present but synthesisReport is absent", () => {
    render(<ParliamentReportSection text="Final synthesis content." />);
    expect(screen.getByText("Structured Parliamentary Report")).toBeInTheDocument();
    expect(screen.getByText(/Structured parliamentary report unavailable; showing recorded synthesis above/)).toBeInTheDocument();
  });

  it("returns null when both synthesisReport and text are absent", () => {
    const { container } = render(<ParliamentReportSection />);
    expect(container.innerHTML).toBe("");
  });

  it("renders DecisionReportView with variant parliament when synthesisReport exists", () => {
    const report = {
      title: "Parliamentary Report",
      executive_summary: "Parliament analysis complete.",
      verdict: {
        recommendation: "Proceed with caution",
        confidence: 0.82,
        decision_type: "proceed",
        rationale: "Strong consensus across models.",
      },
      key_findings: [
        { title: "High confidence", summary: "Models agree.", importance: "high" },
      ],
      quality_meta: {
        verification_status: "verified",
        completeness_score: 0.9,
        faithfulness_score: 0.9,
      },
    };
    render(<ParliamentReportSection synthesisReport={report} text="Synthesis text." />);
    expect(screen.getByText("Parliamentary Report")).toBeInTheDocument();
    expect(screen.getByText("Parliamentary Verification Passed")).toBeInTheDocument();
    expect(screen.queryByText("Structured Parliamentary Report")).not.toBeInTheDocument();
  });

  it("renders real structured report data, not fabricated defaults", () => {
    const report = {
      title: "Real Report",
      verdict: {
        confidence: 0.92,
        decision_type: "proceed",
        rationale: "Evidence-based decision.",
      },
      key_findings: [{ title: "Finding A", summary: "Detail.", importance: "high" }],
    };
    render(<ParliamentReportSection synthesisReport={report} />);
    expect(screen.getByText("Real Report")).toBeInTheDocument();
    expect(screen.getAllByText("92%").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("65%")).not.toBeInTheDocument();
  });
});
