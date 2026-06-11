import React from "react"
import { ShieldCheck, ShieldAlert } from "lucide-react"
import { SemanticAlignmentSection, DivergenceBreakdown } from "./SemanticAlignmentSection"
import { FallbackResponsePanel } from "./FallbackResponsePanel"
import { ReportGenerationFailedCard } from "./ReportGenerationFailedCard"

interface QualityMeta {
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

interface DecisionReportShellProps {
  title?: string
  executiveSummary?: string
  qualityMeta?: QualityMeta
  divergenceBreakdown?: DivergenceBreakdown
  synthesisStatus?: "succeeded" | "failed" | "fallback"
  synthesisError?: string
  fallbackModel?: string
  fallbackReason?: string
  fallbackResponse?: { model: string; content: string }
  isCorrupted?: boolean
  onExport?: () => void
  className?: string
  children?: React.ReactNode
}

export function DecisionReportShell({
  title,
  executiveSummary,
  qualityMeta,
  divergenceBreakdown,
  synthesisStatus = "succeeded",
  synthesisError,
  fallbackModel,
  fallbackReason,
  fallbackResponse,
  isCorrupted = false,
  onExport,
  className,
  children,
}: DecisionReportShellProps) {
  const isFailed = synthesisStatus === "failed" || synthesisStatus === "fallback"

  // Render Quality Gate Status
  const renderQualityGate = () => {
    if (isFailed) {
      return (
        <div className="bg-amber-50/50 dark:bg-amber-950/10 border border-amber-200/30 dark:border-amber-900/30 rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs">
          <div className="flex items-start md:items-center gap-4">
            <div className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/30">
              <ShieldAlert className="h-5 w-5 text-amber-500" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <span className="text-amber-600 dark:text-amber-400">Synthesis Validation Warning</span>
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 max-w-xl leading-relaxed">
                {synthesisError || "The synthesis engine experienced a format validation error. Displaying the top model response as a fallback."}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-6 self-start md:self-auto pt-4 md:pt-0 border-t md:border-t-0 border-slate-200 dark:border-slate-700">
            {divergenceBreakdown?.divergence_score !== undefined && (
              <div className="text-center">
                <span className="text-xs text-slate-500 dark:text-slate-400 block font-medium">Divergence</span>
                <span className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-0.5 block">
                  {Math.round((divergenceBreakdown.divergence_score || 0) * 100)}%
                </span>
              </div>
            )}
          </div>
        </div>
      )
    }

    if (!qualityMeta) return null

    return (
      <div className="bg-slate-50 dark:bg-slate-800/45 border border-slate-200/60 dark:border-slate-800 rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs">
        <div className="flex items-start md:items-center gap-4">
          {qualityMeta.verification_status === "failed" || qualityMeta.has_hallucinations ? (
            <div className="p-2.5 rounded-lg bg-rose-50 dark:bg-rose-950/20 border border-rose-100 dark:border-rose-900/30">
              <ShieldAlert className="h-5 w-5 text-rose-500" />
            </div>
          ) : qualityMeta.verification_status === "unverified" || qualityMeta.verification_error || qualityMeta.needs_revision ? (
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
              Synthesis Quality Gate: {qualityMeta.verification_status === "failed" || qualityMeta.has_hallucinations ? (
                <span className="text-rose-600 dark:text-rose-400">Verification Failed</span>
              ) : qualityMeta.verification_status === "unverified" || qualityMeta.verification_error || qualityMeta.needs_revision ? (
                <span className="text-amber-600 dark:text-amber-400">Unverified</span>
              ) : (
                <span className="text-emerald-600 dark:text-emerald-400">Verified & Faithful</span>
              )}
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 max-w-xl leading-relaxed">
              {qualityMeta.verification_error
                ? (qualityMeta.critic_feedback || "Verifier service temporarily unavailable.")
                : (qualityMeta.critic_feedback || "The final report was cross-verified against all model answers and found to be faithful and complete.")}
            </p>
            {qualityMeta.genericity_risk === "high" && (
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-1 font-medium">
                ⚠ This report may be too generic. Add project-specific context for better results.
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-6 self-start md:self-auto pt-4 md:pt-0 border-t md:border-t-0 border-slate-200 dark:border-slate-700">
          {qualityMeta.completeness_score != null && !qualityMeta.verification_error && (
            <div className="text-center">
              <span className="text-xs text-slate-500 dark:text-slate-400 block font-medium">Completeness</span>
              <span className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-0.5 block">{Math.round((qualityMeta.completeness_score) * 100)}%</span>
            </div>
          )}
          {qualityMeta.faithfulness_score != null && !qualityMeta.verification_error && (
            <div className={`text-center ${qualityMeta.completeness_score != null ? 'border-l border-slate-200 dark:border-slate-700 pl-6' : ''}`}>
              <span className="text-xs text-slate-500 dark:text-slate-400 block font-medium">Faithfulness</span>
              <span className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-0.5 block">{Math.round((qualityMeta.faithfulness_score) * 100)}%</span>
            </div>
          )}
          {qualityMeta.verification_error && (
            <div className="text-center">
              <span className="text-xs text-slate-500 dark:text-slate-400 block font-medium">Scores</span>
              <span className="text-sm font-medium text-amber-600 dark:text-amber-400 mt-0.5 block">Unavailable</span>
            </div>
          )}
          {divergenceBreakdown?.divergence_score !== undefined && (
            <div className={`text-center border-l border-slate-200 dark:border-slate-700 pl-6`}>
              <span className="text-xs text-slate-500 dark:text-slate-400 block font-medium">Divergence</span>
              <span className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-0.5 block">{Math.round((divergenceBreakdown.divergence_score || 0) * 100)}%</span>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={`space-y-8 ${className || ""}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{title || "Decision Report"}</h2>
          {executiveSummary && (
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400 max-w-3xl leading-relaxed">
              {executiveSummary}
            </p>
          )}
        </div>
        {onExport && !isFailed && (
          <button
            onClick={onExport}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 shadow-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
          >
            Export
          </button>
        )}
      </div>

      {/* Quality Gate */}
      {renderQualityGate()}

      {/* Main body content */}
      {isCorrupted ? (
        <ReportGenerationFailedCard reason={qualityMeta?.critic_feedback || "Structured JSON integrity check failed on raw output."} />
      ) : isFailed ? (
        <>
          {fallbackResponse && (
            <FallbackResponsePanel
              modelName={fallbackModel || fallbackResponse.model}
              reason={fallbackReason}
              content={fallbackResponse.content}
            />
          )}
          {divergenceBreakdown && (
            <SemanticAlignmentSection divergenceBreakdown={divergenceBreakdown} />
          )}
        </>
      ) : (
        <>
          {children}
        </>
      )}
    </div>
  )
}
