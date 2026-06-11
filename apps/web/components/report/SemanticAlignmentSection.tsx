"use client"

import { CheckCircle2, GitBranch, AlertTriangle } from "lucide-react"
import { ReportSection } from "./ReportSection"

export interface DivergenceBreakdown {
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

interface SemanticAlignmentSectionProps {
  divergenceBreakdown?: DivergenceBreakdown
}

export function SemanticAlignmentSection({ divergenceBreakdown }: SemanticAlignmentSectionProps) {
  if (!divergenceBreakdown) return null

  const consensusClaims = divergenceBreakdown.consensus_claims || []
  const uniqueInsights = divergenceBreakdown.unique_insights || divergenceBreakdown.contested_claims || []
  const activeContradictions = divergenceBreakdown.active_contradictions || divergenceBreakdown.contradiction_details || []

  return (
    <ReportSection title="Semantic Alignment & Divergence">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Consensus Claims */}
        <div className="bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800/80 rounded-xl p-5">
          <h4 className="text-sm font-semibold text-emerald-800 dark:text-emerald-400 flex items-center gap-2 mb-3">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            Consensus Claims ({consensusClaims.length})
          </h4>
          {consensusClaims.length > 0 ? (
            <div className="space-y-3">
              {consensusClaims.map((c, idx) => (
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
            Unique / Single-Model Insights ({uniqueInsights.length})
          </h4>
          {uniqueInsights.length > 0 ? (
            <div className="space-y-3">
              {uniqueInsights.map((c, idx) => (
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
      {activeContradictions.length > 0 && (
        <div className="mt-6 bg-amber-50/20 dark:bg-amber-950/10 border border-amber-200/30 dark:border-amber-900/30 rounded-xl p-5">
          <h4 className="text-sm font-semibold text-amber-800 dark:text-amber-400 flex items-center gap-2 mb-4">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            Active Contradictions ({activeContradictions.length})
          </h4>
          <div className="space-y-4">
            {activeContradictions.map((c, idx) => (
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
  )
}
