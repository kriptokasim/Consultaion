"use client"

import { cn } from "@/lib/utils"

interface Finding {
  title: string
  summary: string
  importance: string
}

interface KeyFindingsGridProps {
  findings: Finding[]
}

const importanceStyles: Record<string, { dot: string; badge: string }> = {
  critical: { dot: "bg-red-500", badge: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400" },
  high: { dot: "bg-amber-500", badge: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" },
  medium: { dot: "bg-blue-500", badge: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400" },
  low: { dot: "bg-slate-400", badge: "bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-400" },
}

export function KeyFindingsGrid({ findings }: KeyFindingsGridProps) {
  if (!findings.length) return null

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {findings.map((finding, i) => {
        const style = importanceStyles[finding.importance] || importanceStyles.medium
        return (
          <div
            key={i}
            className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-900/40 p-4 space-y-2"
          >
            <div className="flex items-center gap-2">
              <span className={cn("h-2 w-2 rounded-full", style.dot)} />
              <span className={cn("text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full", style.badge)}>
                {finding.importance}
              </span>
            </div>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-white">{finding.title}</h4>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">{finding.summary}</p>
          </div>
        )
      })}
    </div>
  )
}
