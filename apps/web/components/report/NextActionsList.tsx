"use client"

import { cn } from "@/lib/utils"
import { Clock, ArrowRight } from "lucide-react"

interface NextAction {
  action: string
  owner?: string
  priority: string
}

interface NextActionsListProps {
  actions: NextAction[]
}

const priorityConfig: Record<string, { label: string; style: string }> = {
  now: { label: "Now", style: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400" },
  next: { label: "Next", style: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" },
  later: { label: "Later", style: "bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-400" },
}

export function NextActionsList({ actions }: NextActionsListProps) {
  if (!actions.length) return null

  return (
    <div className="space-y-2">
      {actions.map((action, i) => {
        const config = priorityConfig[action.priority] || priorityConfig.next
        return (
          <div
            key={i}
            className="flex items-start gap-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-900/40 p-3"
          >
            <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider", config.style)}>
              {config.label}
            </span>
            <div className="flex-1">
              <p className="text-sm text-slate-900 dark:text-white">{action.action}</p>
              {action.owner && (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Owner: {action.owner}</p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
