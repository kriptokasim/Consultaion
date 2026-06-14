"use client"

import { cn } from "@/lib/utils"

interface Risk {
  item: string
  type: string
  severity: string
  mitigation?: string
}

interface RiskMatrixProps {
  risks: Risk[]
}

const severityStyles: Record<string, { bg: string; text: string }> = {
  critical: { bg: "bg-red-50 dark:bg-red-900/20", text: "text-red-700 dark:text-red-400" },
  high: { bg: "bg-amber-50 dark:bg-amber-900/20", text: "text-amber-700 dark:text-amber-400" },
  medium: { bg: "bg-blue-50 dark:bg-blue-900/20", text: "text-blue-700 dark:text-blue-400" },
  low: { bg: "bg-slate-50 dark:bg-slate-800/50", text: "text-slate-600 dark:text-slate-400" },
}

const typeLabels: Record<string, string> = {
  risk: "Risk",
  assumption: "Assumption",
  unknown: "Unknown",
}

export function RiskMatrix({ risks }: RiskMatrixProps) {
  if (!risks.length) return null

  return (
    <div className="space-y-2">
      {risks.map((risk, i) => {
        const style = severityStyles[risk.severity] || severityStyles.medium
        return (
          <div
            key={i}
            className={cn(
              "flex flex-col sm:flex-row sm:items-start gap-3 rounded-xl border border-slate-200 dark:border-slate-800 p-4 bg-card/65 shadow-xs transition-colors duration-200",
              style.bg
            )}
          >
            <div className="flex items-center gap-2 shrink-0 sm:w-32">
              <span className={cn("text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded", style.text, "bg-background/80 dark:bg-black/20 border border-current/10")}>
                {risk.severity}
              </span>
              <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                {typeLabels[risk.type] || risk.type}
              </span>
            </div>
            <div className="flex-1 space-y-1.5 min-w-0">
              <p className="text-sm font-medium text-slate-850 dark:text-slate-200 leading-relaxed">{risk.item}</p>
              {risk.mitigation && (
                <p className="text-xs text-slate-550 dark:text-slate-450 italic leading-relaxed border-l-2 border-slate-200 dark:border-slate-700 pl-2">
                  <span className="font-semibold not-italic">Mitigation:</span> {risk.mitigation}
                </p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
