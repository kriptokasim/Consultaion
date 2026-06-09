"use client"

import { ConfidenceDonut } from "./ConfidenceDonut"
import { cn } from "@/lib/utils"

interface VerdictCardProps {
  recommendation: string
  confidence: number
  decisionType: string
  rationale: string
}

const typeStyles: Record<string, { bg: string; text: string; label: string }> = {
  proceed: { bg: "bg-emerald-50 dark:bg-emerald-900/20", text: "text-emerald-700 dark:text-emerald-400", label: "Proceed" },
  revise: { bg: "bg-amber-50 dark:bg-amber-900/20", text: "text-amber-700 dark:text-amber-400", label: "Revise" },
  defer: { bg: "bg-blue-50 dark:bg-blue-900/20", text: "text-blue-700 dark:text-blue-400", label: "Defer" },
  reject: { bg: "bg-red-50 dark:bg-red-900/20", text: "text-red-700 dark:text-red-400", label: "Reject" },
  mixed: { bg: "bg-slate-50 dark:bg-slate-800/50", text: "text-slate-700 dark:text-slate-300", label: "Mixed" },
}

export function VerdictCard({ recommendation, confidence, decisionType, rationale }: VerdictCardProps) {
  const style = typeStyles[decisionType] || typeStyles.mixed

  return (
    <div className={cn(
      "rounded-2xl border p-6 shadow-sm",
      "bg-white/80 dark:bg-slate-900/50 border-slate-200 dark:border-slate-800"
    )}>
      <div className="flex items-start gap-6">
        <ConfidenceDonut confidence={confidence} size={96} label="Confidence" />
        <div className="flex-1 space-y-3">
          <div className="flex items-center gap-3">
            <span className={cn("inline-flex items-center rounded-full px-3 py-1 text-sm font-bold", style.bg, style.text)}>
              {style.label}
            </span>
          </div>
          <p className="text-base font-medium text-slate-900 dark:text-white leading-relaxed">
            {recommendation}
          </p>
          {rationale && rationale !== recommendation && (
            <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              {rationale}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
