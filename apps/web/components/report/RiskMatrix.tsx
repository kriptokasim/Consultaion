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
              "flex items-start gap-3 rounded-xl border border-slate-200 dark:border-slate-800 p-3",
              style.bg
            )}
          >
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <span className={cn("text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded", style.text)}>
                {risk.severity}
              </span>
              <span className="text-[10px] font-medium text-slate-500 dark:text-slate-400 uppercase">
                {typeLabels[risk.type] || risk.type}
              </span>
            </div>
            <p className="text-sm text-slate-700 dark:text-slate-300 flex-1">{risk.item}</p>
            {risk.mitigation && (
              <p className="text-xs text-slate-500 dark:text-slate-400 italic flex-1">Mitigation: {risk.mitigation}</p>
            )}
          </div>
        )
      })}
    </div>
  )
}
