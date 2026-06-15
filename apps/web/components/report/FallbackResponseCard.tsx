"use client"

import { AlertTriangle, Sparkles } from "lucide-react"

interface FallbackResponseCardProps {
  model?: string
  reason?: string
  content: string
  className?: string
}

/**
 * Distinct card for fallback responses.
 * Does NOT fabricate confidence scores — shows raw model output transparently.
 */
export function FallbackResponseCard({ model, reason, content, className }: FallbackResponseCardProps) {
  return (
    <div className={`space-y-4 ${className || ""}`}>
      <div className="relative overflow-hidden rounded-xl border border-amber-500/30 bg-amber-50/50 dark:bg-amber-950/10 p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-amber-100 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/30">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-semibold text-amber-800 dark:text-amber-300">
              Fallback Response — No Fabricated Confidence
            </h4>
            <p className="text-xs text-amber-700 dark:text-amber-400/80 mt-1 leading-relaxed">
              {reason || "Synthesis failed or produced invalid output. Displaying raw model response below."}
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-zinc-950 p-4 sm:p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="h-4 w-4 text-indigo-500 dark:text-indigo-400" />
          <h4 className="text-sm font-semibold text-slate-800 dark:text-zinc-200">
            {model ? `${model}` : "Model Response"}
          </h4>
        </div>
        <div className="text-sm text-slate-700 dark:text-zinc-300 whitespace-pre-wrap leading-relaxed">
          {content}
        </div>
      </div>
    </div>
  )
}
