"use client"

import { useMemo } from "react"
import { ReportSection } from "./ReportSection"
import { VerdictCard } from "./VerdictCard"
import { KeyFindingsGrid } from "./KeyFindingsGrid"
import { ModelPositionsTable } from "./ModelPositionsTable"
import { RiskMatrix } from "./RiskMatrix"
import { NextActionsList } from "./NextActionsList"
import { Download, ShieldCheck, CheckCircle2, AlertTriangle, ShieldAlert, GitBranch } from "lucide-react"

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

      {/* Quality Gate Status */}
      {report.quality_meta && (
        <div className="bg-slate-50 dark:bg-slate-800/45 border border-slate-200/60 dark:border-slate-800 rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs">
          <div className="flex items-start md:items-center gap-4">
            {report.quality_meta.verification_status === "failed" || report.quality_meta.has_hallucinations ? (
              <div className="p-2.5 rounded-lg bg-rose-50 dark:bg-rose-950/20 border border-rose-100 dark:border-rose-900/30">
                <ShieldAlert className="h-5 w-5 text-rose-500" />
              </div>
            ) : report.quality_meta.verification_status === "unverified" || report.quality_meta.verification_error || report.quality_meta.needs_revision ? (
              <div className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/30">
                <ShieldAlert className="h-5 w-5 text-amber-500" />
              </div>
            ) : (
              <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-100/30">
                <ShieldCheck className="h-5 w-5 text-emerald-500" />
              </div>
            )}
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                Synthesis Quality Gate: {report.quality_meta.verification_status === "failed" || report.quality_meta.has_hallucinations ? (
                  <span className="text-rose-600 dark:text-rose-400">Verification Failed</span>
                ) : report.quality_meta.verification_status === "unverified" || report.quality_meta.verification_error || report.quality_meta.needs_revision ? (
                  <span className="text-amber-600 dark:text-amber-400">Unverified</span>
                ) : (
                  <span className="text-emerald-600 dark:text-emerald-400">Verified & Faithful</span>
                )}
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 max-w-xl leading-relaxed">
                {report.quality_meta.verification_error
                  ? (report.quality_meta.critic_feedback || "Verifier service temporarily unavailable.")
                  : (report.quality_meta.critic_feedback || "The final report was cross-verified against all model answers and found to be faithful and complete.")}
              </p>
              {report.quality_meta.genericity_risk === "high" && (
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1 font-medium">
                  ⚠ This report may be too generic. Add project-specific context for better results.
                </p>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-6 self-start md:self-auto pt-4 md:pt-0 border-t md:border-t-0 border-slate-200 dark:border-slate-700">
            {report.quality_meta.completeness_score != null && !report.quality_meta.verification_error && (
              <div className="text-center">
                <span className="text-xs text-slate-500 dark:text-slate-400 block font-medium">Completeness</span>
                <span className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-0.5 block">{Math.round((report.quality_meta.completeness_score) * 100)}%</span>
              </div>
            )}
            {report.quality_meta.faithfulness_score != null && !report.quality_meta.verification_error && (
              <div className={`text-center ${report.quality_meta.completeness_score != null ? 'border-l border-slate-200 dark:border-slate-700 pl-6' : ''}`}>
                <span className="text-xs text-slate-500 dark:text-slate-400 block font-medium">Faithfulness</span>
                <span className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-0.5 block">{Math.round((report.quality_meta.faithfulness_score) * 100)}%</span>
              </div>
            )}
            {report.quality_meta.verification_error && (
              <div className="text-center">
                <span className="text-xs text-slate-500 dark:text-slate-400 block font-medium">Scores</span>
                <span className="text-sm font-medium text-amber-600 dark:text-amber-400 mt-0.5 block">Unavailable</span>
              </div>
            )}
            {report.divergence_breakdown?.divergence_score !== undefined && (
              <div className={`text-center border-l border-slate-200 dark:border-slate-700 pl-6`}>
                <span className="text-xs text-slate-500 dark:text-slate-400 block font-medium">Divergence</span>
                <span className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-0.5 block">{Math.round((report.divergence_breakdown.divergence_score || 0) * 100)}%</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Context Needed */}
      {report.context_needed && report.context_needed.length > 0 && (
        <div className="bg-amber-50/50 dark:bg-amber-950/10 border border-amber-200/50 dark:border-amber-900/30 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-amber-800 dark:text-amber-400 flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            Context Needed to Make This Report Specific
          </h3>
          <p className="text-xs text-amber-700 dark:text-amber-400/80 mb-3 leading-relaxed">
            The following information would help generate a more tailored, actionable report:
          </p>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {report.context_needed.map((item, i) => (
              <li key={i} className="text-sm text-amber-800 dark:text-amber-300 flex items-start gap-2">
                <span className="text-amber-400 mt-0.5">•</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

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

      {/* Semantic Alignment & Divergence */}
      {report.divergence_breakdown && (
        <ReportSection title="Semantic Alignment & Divergence">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Consensus Claims */}
            <div className="bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800/80 rounded-xl p-5">
              <h4 className="text-sm font-semibold text-emerald-800 dark:text-emerald-400 flex items-center gap-2 mb-3">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                Consensus Claims ({report.divergence_breakdown.consensus_claims?.length || 0})
              </h4>
              {report.divergence_breakdown.consensus_claims && report.divergence_breakdown.consensus_claims.length > 0 ? (
                <div className="space-y-3">
                  {report.divergence_breakdown.consensus_claims.map((c, idx) => (
                    <div key={idx} className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-850 rounded-lg p-3 shadow-xs">
                      <p className="text-sm text-slate-800 dark:text-slate-200 font-medium">&quot;{c.claim}&quot;</p>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {c.models?.map((m) => (
                          <span key={m} className="inline-flex items-center rounded-md bg-emerald-50 dark:bg-emerald-950/35 px-1.5 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-400 border border-emerald-200/10">
                            {m}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 dark:text-slate-400 italic">No consensus claims identified.</p>
              )}
            </div>

            {/* Unique / Single-Model Insights */}
            <div className="bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800/80 rounded-xl p-5">
              <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-2 mb-3">
                <GitBranch className="h-4 w-4 text-slate-400" />
                Unique / Single-Model Insights ({(report.divergence_breakdown.unique_insights || report.divergence_breakdown.contested_claims)?.length || 0})
              </h4>
              {((report.divergence_breakdown.unique_insights || report.divergence_breakdown.contested_claims)?.length || 0) > 0 ? (
                <div className="space-y-3">
                  {(report.divergence_breakdown.unique_insights || report.divergence_breakdown.contested_claims || []).map((c, idx) => (
                    <div key={idx} className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-850 rounded-lg p-3 shadow-xs">
                      <p className="text-sm text-slate-800 dark:text-slate-200 font-medium">&quot;{c.claim}&quot;</p>
                      <div className="mt-2">
                        <span className="inline-flex items-center rounded-md bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 text-xs font-medium text-slate-700 dark:text-slate-300 border border-slate-200/10">
                          {c.model}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 dark:text-slate-400 italic">No unique insights identified.</p>
              )}
            </div>
          </div>

          {/* Active Contradictions — only shown when there are actual contradictions */}
          {((report.divergence_breakdown.active_contradictions || report.divergence_breakdown.contradiction_details) ?? []).length > 0 && (
            <div className="mt-6 bg-amber-50/20 dark:bg-amber-950/10 border border-amber-200/30 dark:border-amber-900/30 rounded-xl p-5">
              <h4 className="text-sm font-semibold text-amber-800 dark:text-amber-400 flex items-center gap-2 mb-4">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                Active Contradictions ({(report.divergence_breakdown.active_contradictions || report.divergence_breakdown.contradiction_details || []).length})
              </h4>
              <div className="space-y-4">
                {(report.divergence_breakdown.active_contradictions || report.divergence_breakdown.contradiction_details || []).map((c, idx) => (
                  <div key={idx} className="bg-white dark:bg-slate-900 border border-amber-200/30 dark:border-amber-900/20 rounded-lg p-4 shadow-xs">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 block mb-1">{c.model_a} claim:</span>
                        <p className="text-sm text-slate-800 dark:text-slate-200 italic font-medium">&quot;{c.claim_a}&quot;</p>
                      </div>
                      <div className="border-t md:border-t-0 md:border-l border-slate-100 dark:border-slate-800 pt-3 md:pt-0 md:pl-4">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 block mb-1">{c.model_b} claim:</span>
                        <p className="text-sm text-slate-800 dark:text-slate-200 italic font-medium">&quot;{c.claim_b}&quot;</p>
                      </div>
                    </div>
                    <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800">
                      <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 block mb-1">Divergence explanation:</span>
                      <p className="text-xs text-amber-800 dark:text-amber-400 leading-relaxed">{c.reason}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
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
