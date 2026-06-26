import React from "react"
import { ShieldCheck, ShieldAlert, Maximize2, Minimize2, Compass, BookOpen } from "lucide-react"
import { SemanticAlignmentSection, DivergenceBreakdown } from "./SemanticAlignmentSection"
import { FallbackResponseCard } from "./FallbackResponseCard"
import { ReportGenerationFailedCard } from "./ReportGenerationFailedCard"
import { ReportSectionNav } from "./ReportSectionNav"

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
  variant?: "arena" | "parliament"
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
  variant = "arena",
  children,
}: DecisionReportShellProps) {
  const isFailed = synthesisStatus === "failed" || synthesisStatus === "fallback"
  const [isFocusMode, setIsFocusMode] = React.useState(false)
  const [tocOpen, setTocOpen] = React.useState(false)

  React.useEffect(() => {
    if (isFocusMode) {
      document.body.style.overflow = "hidden"
      document.body.style.overscrollBehavior = "contain"
    } else {
      document.body.style.overflow = ""
      document.body.style.overscrollBehavior = ""
    }
    return () => {
      document.body.style.overflow = ""
      document.body.style.overscrollBehavior = ""
    }
  }, [isFocusMode])

  const [activeSections, setActiveSections] = React.useState<Array<{ id: string, label: string }>>([])

  React.useEffect(() => {
    const rawSections = [
      { id: "report-verdict", label: "Verdict" },
      { id: "report-findings", label: "Key Findings" },
      { id: "report-positions", label: "Model Positions" },
      { id: "report-risks", label: "Risks & Assumptions" },
      { id: "report-actions", label: "Next Actions" },
      { id: "report-caveats", label: "Caveats" },
    ]
    const active = rawSections.filter((s) => !!document.getElementById(s.id))
    setActiveSections(active)
  }, [children])

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      setTocOpen(false);
    }
  };

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
              {synthesisError || (variant === "parliament"
                ? "The parliamentary synthesis engine experienced a format validation error. Showing the recorded synthesis above."
                : "The synthesis engine experienced a format validation error. Displaying the top model response as a fallback.")}
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
                <span className="text-emerald-600 dark:text-emerald-400">
                  {variant === "parliament" ? "Parliamentary Verification Passed" : "Verified & Faithful"}
                </span>
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

  const contentMarkup = (
    <>
      {/* Quality Gate */}
      {renderQualityGate()}

      {/* Main body content */}
      {isCorrupted ? (
        <ReportGenerationFailedCard reason={qualityMeta?.critic_feedback || "Structured JSON integrity check failed on raw output."} />
      ) : isFailed ? (
        <>
          {fallbackResponse && (
            <FallbackResponseCard
              model={fallbackModel || fallbackResponse.model}
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
    </>
  )

  if (isFocusMode) {
    return (
      <div className="fixed inset-0 z-50 bg-background dark:bg-stone-950 flex flex-col animate-in fade-in duration-200">
        {/* Sticky top header */}
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-background/90 px-4 py-3.5 backdrop-blur-md">
          <div className="flex items-center gap-2 min-w-0">
            <BookOpen className="h-5 w-5 text-primary shrink-0" />
            <h1 className="text-sm sm:text-base font-bold text-foreground truncate">
              {title || "Decision Report"} (Focus Mode)
            </h1>
          </div>
          <div className="flex items-center gap-2">
            {onExport && !isFailed && (
              <button
                onClick={onExport}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-foreground shadow-sm hover:bg-muted/40 transition"
              >
                Export
              </button>
            )}
            <button
              onClick={() => setIsFocusMode(false)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-foreground shadow-sm hover:bg-muted/40 transition"
            >
              <Minimize2 className="h-3.5 w-3.5" />
              Exit Focus
            </button>
          </div>
        </header>

        {/* Focus Mode Scrollable Body Container */}
        <div className="flex-1 overflow-y-auto px-4 py-8 sm:px-8 max-w-4xl mx-auto w-full space-y-8 pb-24 scroll-smooth">
          {executiveSummary && (
            <p className="text-sm sm:text-base text-slate-700 dark:text-slate-300 leading-relaxed font-medium bg-muted/20 border border-border/40 p-4 rounded-xl">
              {executiveSummary}
            </p>
          )}
          {contentMarkup}
        </div>

        {/* Floating Table of Contents for Focus Mode */}
        {activeSections.length > 0 && (
          <div className="fixed bottom-4 right-4 z-40">
            <div className="relative">
              {tocOpen && (
                <div className="absolute bottom-12 right-0 bg-card border border-border rounded-xl shadow-lg p-3 w-56 space-y-1 animate-in slide-in-from-bottom-2 fade-in duration-150">
                  <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider px-2 pb-1.5 border-b border-border/60">
                    Jump to Section
                  </p>
                  {activeSections.map((sec) => (
                    <button
                      key={sec.id}
                      onClick={() => scrollToSection(sec.id)}
                      className="w-full text-left px-2 py-1.5 text-xs font-medium text-foreground rounded-lg hover:bg-muted/50 transition truncate block"
                    >
                      {sec.label}
                    </button>
                  ))}
                </div>
              )}
              <button
                onClick={() => setTocOpen(!tocOpen)}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/95 transition-all active:scale-95"
              >
                <Compass className="h-5 w-5" />
              </button>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={`space-y-8 ${className || ""}`}>
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white truncate">{title || "Decision Report"}</h2>
          {executiveSummary && (
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400 max-w-3xl leading-relaxed hidden sm:block">
              {executiveSummary}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setIsFocusMode(true)}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 py-2 text-sm font-medium text-slate-755 dark:text-slate-300 shadow-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition"
          >
            <Maximize2 className="h-4 w-4" />
            <span className="hidden sm:inline">Focus Mode</span>
          </button>
          {onExport && !isFailed && (
            <button
              onClick={onExport}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 shadow-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
            >
              Export
            </button>
          )}
        </div>
      </div>

      {executiveSummary && (
        <p className="text-sm text-slate-600 dark:text-slate-400 max-w-3xl leading-relaxed sm:hidden">
          {executiveSummary}
        </p>
      )}

      {/* Navigation */}
      {!isFailed && activeSections.length > 0 && (
        <ReportSectionNav sections={activeSections} className="rounded-xl border border-border/30 overflow-hidden shadow-xs" />
      )}

      {contentMarkup}

    </div>
  )
}
