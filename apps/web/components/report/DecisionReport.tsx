"use client";

import { DecisionReportView, type DecisionReport as DecisionReportData } from "./DecisionReportView";

export interface DecisionReportRun {
  report: DecisionReportData | null;
  rawSynthesis?: string;
  synthesisStatus?: "pending" | "succeeded" | "failed" | "fallback";
  synthesisError?: string;
  fallbackModel?: string;
  fallbackReason?: string;
  fallbackResponse?: { model?: string; content?: string } | null;
  divergenceBreakdown?: any;
  variant?: "arena" | "parliament";
}

export interface DecisionReportProps {
  run: DecisionReportRun;
  /**
   * run end = record, share = brief, export = record, print = record
   * (NEW_UX_PATCHSET PS06).
   */
  audience: "brief" | "record";
  className?: string;
}

/**
 * PS06 canonical entry point: DecisionReport({ run, audience }).
 *
 * A thin adapter over DecisionReportView/DecisionReportShell, which keep
 * owning report integrity, verification, and failed/fallback/unstructured
 * rendering unchanged — none of that logic was touched to build this. The
 * report stays on the paper surface even when this is rendered inside the
 * ink app shell (DESIGN-SPEC "Report remains paper inside the ink app").
 */
export function DecisionReport({ run, audience, className }: DecisionReportProps) {
  return (
    <DecisionReportView
      report={run.report}
      rawSynthesis={run.rawSynthesis}
      variant={run.variant}
      showChrome={audience === "record"}
      synthesisStatus={run.synthesisStatus}
      synthesisError={run.synthesisError}
      fallbackModel={run.fallbackModel}
      fallbackReason={run.fallbackReason}
      fallbackResponse={run.fallbackResponse}
      divergenceBreakdown={run.divergenceBreakdown}
      audience={audience}
      className={`new-ux-report-paper ${className || ""}`.trim()}
    />
  );
}
