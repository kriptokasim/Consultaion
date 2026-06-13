"use client"

import React, { useMemo } from "react"
import { ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2, GitBranch, Trophy, Flame } from "lucide-react"
import { ConfidenceDonut } from "./ConfidenceDonut"
import { cn } from "@/lib/utils"

interface DecisionBriefProps {
  verdict: {
    recommendation?: string
    confidence?: number
    decision_type?: string
    rationale?: string
  }
  modelPositions: Array<{
    model?: string
    stance?: string
    strongest_point?: string
    concern?: string
  }>
  divergenceBreakdown?: {
    divergence_score?: number
    consensus_claims?: Array<any>
    unique_insights?: Array<any>
    contested_claims?: Array<any>
    active_contradictions?: Array<any>
    contradiction_details?: Array<any>
  }
  scores?: Array<{
    persona: string
    score: number
  }>
}

const typeStyles: Record<string, { bg: string; text: string; label: string; border: string }> = {
  proceed: { bg: "bg-emerald-50 dark:bg-emerald-950/30", text: "text-emerald-700 dark:text-emerald-400", border: "border-emerald-200 dark:border-emerald-800", label: "Proceed" },
  revise: { bg: "bg-amber-50 dark:bg-amber-950/30", text: "text-amber-700 dark:text-amber-400", border: "border-amber-200 dark:border-amber-800", label: "Revise" },
  defer: { bg: "bg-blue-50 dark:bg-blue-950/30", text: "text-blue-700 dark:text-blue-450", border: "border-blue-200 dark:border-blue-800", label: "Defer" },
  reject: { bg: "bg-red-50 dark:bg-red-950/30", text: "text-red-700 dark:text-red-400", border: "border-red-200 dark:border-red-800", label: "Reject" },
  mixed: { bg: "bg-slate-50 dark:bg-slate-800/40", text: "text-slate-700 dark:text-slate-300", border: "border-slate-200 dark:border-slate-800", label: "Mixed" },
}

export function DecisionBrief({
  verdict,
  modelPositions = [],
  divergenceBreakdown,
  scores = [],
}: DecisionBriefProps) {
  const decisionType = (verdict.decision_type || "mixed").toLowerCase()
  const style = typeStyles[decisionType] || typeStyles.mixed

  // 1. Calculate contradiction density and claims breakdown
  const consensusCount = divergenceBreakdown?.consensus_claims?.length || 0
  const uniqueCount = divergenceBreakdown?.unique_insights?.length || divergenceBreakdown?.contested_claims?.length || 0
  const contradictionCount = divergenceBreakdown?.active_contradictions?.length || divergenceBreakdown?.contradiction_details?.length || 0
  const totalClaims = consensusCount + uniqueCount + contradictionCount
  
  const divergenceScore = divergenceBreakdown?.divergence_score ?? (totalClaims > 0 ? contradictionCount / totalClaims : 0)

  // 2. Determine win rate leaderboard
  // If we have explicit scores, rank by score. Otherwise, rank by supportive stances.
  const leaderboard = useMemo(() => {
    if (scores && scores.length > 0) {
      return scores
        .slice()
        .sort((a, b) => b.score - a.score)
        .map((s, idx) => ({
          name: s.persona,
          score: s.score,
          rank: idx + 1,
          isWinner: idx === 0,
        }))
    }
    // Fallback ranking based on stance
    return modelPositions.map((pos, idx) => {
      const isSupportive = pos.stance?.toLowerCase() === "supportive"
      const score = isSupportive ? 9.0 : pos.stance?.toLowerCase() === "neutral" ? 7.0 : 5.0
      return {
        name: pos.model || `Agent ${idx + 1}`,
        score,
        rank: idx + 1,
        isWinner: idx === 0 && isSupportive,
      }
    }).sort((a, b) => b.score - a.score)
  }, [scores, modelPositions])

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
      {/* Column 1: Verdict & Confidence */}
      <div className={cn(
        "rounded-2xl border p-5 bg-card/60 flex flex-col justify-between shadow-sm relative overflow-hidden",
        style.border
      )}>
        <div className="absolute top-0 right-0 h-24 w-24 bg-primary/5 rounded-full blur-xl -mr-6 -mt-6 pointer-events-none" />
        
        <div>
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Final Decision Verdict
            </span>
            <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide border", style.bg, style.text, style.border)}>
              {style.label}
            </span>
          </div>

          <div className="flex items-center gap-4">
            <ConfidenceDonut confidence={verdict.confidence ?? 0.75} size={70} label="" />
            <div className="space-y-1">
              <span className="text-2xl font-bold text-foreground">
                {Math.round((verdict.confidence ?? 0.75) * 100)}%
              </span>
              <p className="text-xs text-muted-foreground font-medium">Confidence Score</p>
            </div>
          </div>
        </div>

        <p className="mt-4 text-xs text-foreground/80 leading-relaxed italic border-t border-border/60 pt-3">
          &ldquo;{verdict.recommendation || "Synthesis evaluation complete."}&rdquo;
        </p>
      </div>

      {/* Column 2: Stance Leaderboard / Win Rates */}
      <div className="rounded-2xl border border-border bg-card/60 p-5 flex flex-col justify-between shadow-sm">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-1.5">
            <Trophy className="h-4 w-4 text-amber-500" />
            Model Contribution Leaderboard
          </h3>

          <div className="space-y-2.5">
            {leaderboard.slice(0, 3).map((item, idx) => (
              <div key={item.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className={cn(
                    "flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold border",
                    item.isWinner
                      ? "bg-amber-100 text-amber-800 border-amber-250 dark:bg-amber-900/40 dark:text-amber-300"
                      : "bg-muted text-muted-foreground border-border"
                  )}>
                    {item.rank}
                  </span>
                  <span className="font-semibold text-foreground truncate max-w-[120px]">
                    {item.name}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                      className={cn("h-full rounded-full", item.isWinner ? "bg-amber-500" : "bg-muted-foreground/35")}
                      style={{ width: `${(item.score / 10) * 100}%` }}
                    />
                  </div>
                  <span className="font-mono text-muted-foreground font-semibold">
                    {item.score.toFixed(1)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="mt-4 text-[10px] text-muted-foreground leading-relaxed border-t border-border/60 pt-3">
          Scores reflect argument rigor, stance consistency, and consensus alignment.
        </p>
      </div>

      {/* Column 3: Contradiction Density Chart */}
      <div className="rounded-2xl border border-border bg-card/60 p-5 flex flex-col justify-between shadow-sm">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-1.5">
            <Flame className="h-4 w-4 text-rose-500 animate-pulse" />
            Contradiction Density Chart
          </h3>

          <div className="space-y-3">
            <div className="flex justify-between items-end text-xs">
              <span className="font-semibold text-foreground">
                {Math.round(divergenceScore * 100)}% Divergence
              </span>
              <span className="text-[10px] text-muted-foreground">
                {contradictionCount} Active Contradictions
              </span>
            </div>

            {/* Stacked segment chart representing Claims breakdown */}
            <div className="h-3 w-full rounded-full overflow-hidden flex bg-muted border border-border/40">
              <div
                className="h-full bg-emerald-500 transition-all duration-300"
                style={{ width: `${totalClaims > 0 ? (consensusCount / totalClaims) * 100 : 40}%` }}
                title={`${consensusCount} Consensus Claims`}
              />
              <div
                className="h-full bg-blue-500 transition-all duration-300 border-l border-card"
                style={{ width: `${totalClaims > 0 ? (uniqueCount / totalClaims) * 100 : 40}%` }}
                title={`${uniqueCount} Unique Insights`}
              />
              <div
                className="h-full bg-amber-500 transition-all duration-300 border-l border-card"
                style={{ width: `${totalClaims > 0 ? (contradictionCount / totalClaims) * 100 : 20}%` }}
                title={`${contradictionCount} Contradictions`}
              />
            </div>

            {/* Custom chart legend */}
            <div className="flex flex-wrap gap-x-3 gap-y-1.5 text-[9px] font-medium text-muted-foreground pt-1">
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Consensus ({consensusCount})
              </span>
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
                Unique ({uniqueCount})
              </span>
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                Contradicted ({contradictionCount})
              </span>
            </div>
          </div>
        </div>

        <p className="mt-4 text-[10px] text-muted-foreground leading-relaxed border-t border-border/60 pt-3">
          Higher divergence indicates conflicting agent theories or critical trade-offs.
        </p>
      </div>
    </div>
  )
}
