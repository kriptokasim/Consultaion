import React from "react"
import { AlertTriangle, Sparkles } from "lucide-react"

interface FallbackResponsePanelProps {
  modelName: string
  reason?: string
  content: string
}

export function FallbackResponsePanel({ modelName, reason, content }: FallbackResponsePanelProps) {
  return (
    <div className="space-y-6">
      <div className="relative overflow-hidden rounded-2xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-zinc-900/90 to-zinc-950 p-6 shadow-2xl backdrop-blur-md md:p-8">
        {/* Decorative ambient background blur */}
        <div className="absolute -right-16 -top-16 h-36 w-36 rounded-full bg-amber-500/10 blur-3xl" />
        <div className="absolute -left-16 -bottom-16 h-36 w-36 rounded-full bg-amber-600/10 blur-3xl" />

        <div className="flex flex-col items-start gap-4 sm:flex-row sm:gap-6">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20">
            <AlertTriangle className="h-6 w-6" />
          </div>

          <div className="flex-1 space-y-4">
            <div>
              <h3 className="text-lg font-semibold tracking-tight text-amber-200 sm:text-xl">
                Synthesis Fallback Mode Active
              </h3>
              <p className="mt-1 text-sm leading-relaxed text-zinc-400">
                An error occurred during structured synthesis or the generated report did not pass our strict quality gates. 
                Displaying the top model response as a fallback to preserve the analysis quality.
              </p>
            </div>

            {reason && (
              <div className="rounded-lg border border-amber-500/10 bg-amber-500/5 p-3.5">
                <span className="text-xs font-semibold uppercase tracking-wider text-amber-400 block mb-1">
                  Diagnostics:
                </span>
                <code className="text-xs font-mono text-zinc-300 break-words leading-relaxed">
                  {reason}
                </code>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Fallback response content panel */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-zinc-950 p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 ring-1 ring-indigo-500/20">
            <Sparkles className="h-4 w-4" />
          </div>
          <h4 className="text-sm font-semibold text-slate-800 dark:text-zinc-200">
            Top Model Response: {modelName}
          </h4>
        </div>
        <div className="prose prose-slate dark:prose-invert max-w-none">
          <div className="text-sm text-slate-755 dark:text-zinc-300 whitespace-pre-wrap leading-relaxed">
            {content}
          </div>
        </div>
      </div>
    </div>
  )
}
