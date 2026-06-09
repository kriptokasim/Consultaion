"use client"

import { useMemo } from "react"
import { ReportSection } from "./ReportSection"
import { VerdictCard } from "./VerdictCard"
import { KeyFindingsGrid } from "./KeyFindingsGrid"
import { ModelPositionsTable } from "./ModelPositionsTable"
import { RiskMatrix } from "./RiskMatrix"
import { NextActionsList } from "./NextActionsList"
import { Download } from "lucide-react"

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
}

interface DecisionReportViewProps {
  report: DecisionReport | null
  rawSynthesis?: string
  className?: string
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

export function DecisionReportView({ report: rawReport, rawSynthesis, className }: DecisionReportViewProps) {
  const report = useMemo(() => {
    if (rawReport && rawReport.verdict) return rawReport
    if (rawSynthesis) return buildFallbackReport(rawSynthesis)
    return null
  }, [rawReport, rawSynthesis])

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

  return (
    <div className={`space-y-8 ${className || ""}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{report.title || "Decision Report"}</h2>
          {report.executive_summary && (
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400 max-w-3xl leading-relaxed">
              {report.executive_summary}
            </p>
          )}
        </div>
        <button
          onClick={handleExport}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 shadow-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
        >
          <Download className="h-4 w-4" />
          Export
        </button>
      </div>

      {/* Verdict */}
      {report.verdict && (
        <ReportSection title="Verdict">
          <VerdictCard
            recommendation={report.verdict.recommendation || ""}
            confidence={report.verdict.confidence || 0.5}
            decisionType={report.verdict.decision_type || "mixed"}
            rationale={report.verdict.rationale || ""}
          />
        </ReportSection>
      )}

      {/* Key Findings */}
      {report.key_findings && report.key_findings.length > 0 && (
        <ReportSection title="Key Findings">
          <KeyFindingsGrid findings={report.key_findings as any} />
        </ReportSection>
      )}

      {/* Model Positions */}
      {report.model_positions && report.model_positions.length > 0 && (
        <ReportSection title="Model Positions">
          <ModelPositionsTable positions={report.model_positions as any} />
        </ReportSection>
      )}

      {/* Risks & Assumptions */}
      {report.risks_and_assumptions && report.risks_and_assumptions.length > 0 && (
        <ReportSection title="Risks & Assumptions">
          <RiskMatrix risks={report.risks_and_assumptions as any} />
        </ReportSection>
      )}

      {/* Next Actions */}
      {report.next_actions && report.next_actions.length > 0 && (
        <ReportSection title="Next Actions">
          <NextActionsList actions={report.next_actions as any} />
        </ReportSection>
      )}

      {/* Caveats */}
      {report.caveats && report.caveats.length > 0 && (
        <ReportSection title="Caveats">
          <ul className="space-y-1">
            {report.caveats.map((caveat, i) => (
              <li key={i} className="text-sm text-slate-600 dark:text-slate-400 flex items-start gap-2">
                <span className="text-slate-400 dark:text-slate-500 mt-0.5">-</span>
                {caveat}
              </li>
            ))}
          </ul>
        </ReportSection>
      )}
    </div>
  )
}
