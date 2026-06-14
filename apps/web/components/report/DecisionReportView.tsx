"use client"

import { useMemo } from "react"
import { ReportSection } from "./ReportSection"
import { VerdictCard } from "./VerdictCard"
import { KeyFindingsGrid } from "./KeyFindingsGrid"
import { ModelPositionsTable } from "./ModelPositionsTable"
import { RiskMatrix } from "./RiskMatrix"
import { NextActionsList } from "./NextActionsList"
import { Download, ShieldCheck, CheckCircle2, AlertTriangle, ShieldAlert, GitBranch } from "lucide-react"
import { isRenderableDecisionReport, fieldLooksCorrupt } from "../../lib/reportIntegrity"
import { ReportGenerationFailedCard } from "./ReportGenerationFailedCard"
import { SemanticAlignmentSection } from "./SemanticAlignmentSection"
import { DecisionReportShell } from "./DecisionReportShell"
import { DecisionBrief } from "./DecisionBrief"

interface DecisionReport {
  title?: string
  executive_summary?: string
  verdict?: {
    recommendation?: string
    confidence?: number
    decision_type?: string
    rationale?: string
  }
  key_findings?: Array<{
    title?: string
    summary?: string
    importance?: string
  }>
  model_positions?: Array<{
    model?: string
    stance?: string
    distinct_contribution?: string
    blind_spot?: string
    strongest_point?: string
    concern?: string
  }>
  risks_and_assumptions?: Array<{
    item?: string
    type?: string
    severity?: string
    mitigation?: string
  }>
  next_actions?: Array<{
    action?: string
    owner?: string
    priority?: string
  }>
  caveats?: string[]
  options_considered?: Array<{
    option?: string
    pros?: string[]
    cons?: string[]
    score?: number
  }>
  quality_meta?: {
    completeness_score?: number | null
    faithfulness_score?: number | null
    has_hallucinations?: boolean
    needs_revision?: boolean
    critic_feedback?: string
    verification_status?: string
    verification_error?: boolean
    verification_source?: string
    specificity_score?: number | null
    genericity_risk?: string
  }
  context_needed?: string[]
  divergence_breakdown?: {
    divergence_score?: number
    consensus_claims?: Array<{ claim: string; models: string[] }>
    unique_insights?: Array<{ claim: string; model: string }>
    contested_claims?: Array<{ claim: string; model: string }>
    active_contradictions?: Array<{
      claim_a: string
      model_a: string
      claim_b: string
      model_b: string
      reason: string
    }>
    contradictions_count?: number
    contradiction_details?: Array<{
      claim_a: string
      model_a: string
      claim_b: string
      model_b: string
      reason: string
    }>
  }
}

interface DecisionReportViewProps {
  report: DecisionReport | null
  rawSynthesis?: string
  className?: string
  synthesisStatus?: "succeeded" | "failed" | "fallback"
  synthesisError?: string
  fallbackModel?: string
  fallbackReason?: string
  fallbackResponse?: { model: string; content: string }
}

function buildFallbackReport(rawSynthesis: string): DecisionReport {
  return {
    title: "Decision Report",
    executive_summary: rawSynthesis.slice(0, 500),
    verdict: {
      recommendation: rawSynthesis.slice(0, 300),
      confidence: 0.5,
      decision_type: "mixed",
      rationale: rawSynthesis.slice(0, 500),
    },
    key_findings: [],
    model_positions: [],
    risks_and_assumptions: [],
    next_actions: [],
    caveats: [],
  }
}

function exportToMarkdown(report: DecisionReport): string {
  const lines: string[] = []
  lines.push(`# ${report.title || "Decision Report"}`)
  lines.push("")

  if (report.executive_summary) {
    lines.push("## Executive Summary")
    lines.push(report.executive_summary)
    lines.push("")
  }

  if (report.verdict) {
    lines.push("## Verdict")
    lines.push(`**Recommendation:** ${report.verdict.decision_type?.toUpperCase() || "MIXED"}`)
    lines.push(`**Confidence:** ${Math.round((report.verdict.confidence || 0) * 100)}%`)
    lines.push(`**Rationale:** ${report.verdict.rationale || report.verdict.recommendation || ""}`)
    lines.push("")
  }

  if (report.key_findings?.length) {
    lines.push("## Key Findings")
    report.key_findings.forEach((f, i) => {
      lines.push(`${i + 1}. **[${f.importance?.toUpperCase() || "MEDIUM"}]** ${f.title}: ${f.summary}`)
    })
    lines.push("")
  }

  if (report.model_positions?.length) {
    lines.push("## Model Positions")
    report.model_positions.forEach((p) => {
      lines.push(`- **${p.model}** (${p.stance}): ${p.strongest_point}`)
      if (p.concern) lines.push(`  - Concern: ${p.concern}`)
    })
    lines.push("")
  }

  if (report.risks_and_assumptions?.length) {
    lines.push("## Risks & Assumptions")
    report.risks_and_assumptions.forEach((r) => {
      lines.push(`- [${r.severity?.toUpperCase() || "MEDIUM"}] (${r.type}): ${r.item}`)
      if (r.mitigation) lines.push(`  - Mitigation: ${r.mitigation}`)
    })
    lines.push("")
  }

  if (report.next_actions?.length) {
    lines.push("## Next Actions")
    report.next_actions.forEach((a) => {
      lines.push(`- [${a.priority?.toUpperCase() || "NEXT"}] ${a.action}`)
    })
    lines.push("")
  }

  if (report.caveats?.length) {
    lines.push("## Caveats")
    report.caveats.forEach((c) => lines.push(`- ${c}`))
    lines.push("")
  }

  return lines.join("\n")
}

export function DecisionReportView({
  report: rawReport,
  rawSynthesis,
  className,
}: DecisionReportViewProps) {
  const isCorrupted = useMemo(() => {
    if (rawReport && !isRenderableDecisionReport(rawReport)) {
      return true
    }
    if (!rawReport && rawSynthesis && fieldLooksCorrupt(rawSynthesis)) {
      return true
    }
    return false
  }, [rawReport, rawSynthesis])

  const report = useMemo(() => {
    if (isCorrupted) return null
    if (rawReport && rawReport.verdict) return rawReport
    if (rawSynthesis) return buildFallbackReport(rawSynthesis)
    return null
  }, [rawReport, rawSynthesis, isCorrupted])

  if (isCorrupted) {
    const errorDetails = rawReport?.quality_meta?.critic_feedback || "Structured JSON integrity check failed on raw output."
    return (
      <div className={className}>
        <ReportGenerationFailedCard reason={errorDetails} />
      </div>
    )
  }

  if (!report) return null

  const handleExport = () => {
    const md = exportToMarkdown(report)
    const blob = new Blob([md], { type: "text/markdown" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `decision-report-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const activeReport = report

  return (
    <DecisionReportShell
      title={activeReport.title}
      executiveSummary={activeReport.executive_summary}
      qualityMeta={activeReport.quality_meta}
      divergenceBreakdown={activeReport.divergence_breakdown || rawReport?.divergence_breakdown}
      isCorrupted={isCorrupted}
      onExport={handleExport}
      className={className}
    >
      {/* Decision Stance, Stance Leaderboard, Contradiction Density */}
      <DecisionBrief
        verdict={activeReport.verdict || {}}
        modelPositions={activeReport.model_positions || []}
        divergenceBreakdown={activeReport.divergence_breakdown || rawReport?.divergence_breakdown}
        scores={(activeReport.quality_meta as any)?.scores || []}
      />

      {/* Context Needed */}
      {activeReport.context_needed && activeReport.context_needed.length > 0 && (
        <div className="bg-amber-50/50 dark:bg-amber-950/10 border border-amber-200/50 dark:border-amber-900/30 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-amber-800 dark:text-amber-400 flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            Context Needed to Make This Report Specific
          </h3>
          <p className="text-xs text-amber-700 dark:text-amber-400/80 mb-3 leading-relaxed">
            The following information would help generate a more tailored, actionable report:
          </p>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {activeReport.context_needed.map((item, i) => (
              <li key={i} className="text-sm text-amber-800 dark:text-amber-300 flex items-start gap-2">
                <span className="text-amber-400 mt-0.5">•</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Verdict */}
      {activeReport.verdict && (
        <ReportSection id="report-verdict" title="Verdict">
          <VerdictCard
            recommendation={activeReport.verdict.recommendation || ""}
            confidence={activeReport.verdict.confidence || 0.5}
            decisionType={activeReport.verdict.decision_type || "mixed"}
            rationale={activeReport.verdict.rationale || ""}
          />
        </ReportSection>
      )}

      {/* Key Findings */}
      {activeReport.key_findings && activeReport.key_findings.length > 0 && (
        <ReportSection id="report-findings" title="Key Findings">
          <KeyFindingsGrid findings={activeReport.key_findings as any} />
        </ReportSection>
      )}

      {/* Model Positions */}
      {activeReport.model_positions && activeReport.model_positions.length > 0 && (
        <ReportSection id="report-positions" title="Model Positions">
          <ModelPositionsTable positions={activeReport.model_positions as any} />
        </ReportSection>
      )}

      {/* Semantic Alignment & Divergence */}
      {activeReport.divergence_breakdown && (
        <SemanticAlignmentSection divergenceBreakdown={activeReport.divergence_breakdown} />
      )}

      {/* Risks & Assumptions */}
      {activeReport.risks_and_assumptions && activeReport.risks_and_assumptions.length > 0 && (
        <ReportSection id="report-risks" title="Risks & Assumptions">
          <RiskMatrix risks={activeReport.risks_and_assumptions as any} />
        </ReportSection>
      )}

      {/* Next Actions */}
      {activeReport.next_actions && activeReport.next_actions.length > 0 && (
        <ReportSection id="report-actions" title="Next Actions">
          <NextActionsList actions={activeReport.next_actions as any} />
        </ReportSection>
      )}

      {/* Caveats */}
      {activeReport.caveats && activeReport.caveats.length > 0 && (
        <ReportSection id="report-caveats" title="Caveats">
          <ul className="space-y-1">
            {activeReport.caveats.map((caveat, i) => (
              <li key={i} className="text-sm text-slate-600 dark:text-slate-400 flex items-start gap-2">
                <span className="text-slate-400 dark:text-slate-500 mt-0.5">-</span>
                {caveat}
              </li>
            ))}
          </ul>
        </ReportSection>
      )}
    </DecisionReportShell>
  )
}
