"use client"

import { FileText, Sparkles } from "lucide-react"

interface UnstructuredSynthesisCardProps {
  content: string
  className?: string
}

/**
 * Renders raw unstructured synthesis.
 * Does NOT fabricate confidence scores or build structured mock reports.
 */
export function UnstructuredSynthesisCard({ content, className }: UnstructuredSynthesisCardProps) {
  return (
    <div className={`space-y-4 ${className || ""}`}>
      <div className="relative overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-zinc-900/10 p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-slate-700">
            <FileText className="h-4 w-4 text-slate-600 dark:text-slate-400" />
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-semibold text-slate-800 dark:text-zinc-200">
              Unstructured Synthesis Output
            </h4>
            <p className="text-xs text-slate-600 dark:text-zinc-400 mt-1 leading-relaxed">
              No structured JSON report was generated. Displaying raw synthesis response below.
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-zinc-950 p-4 sm:p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="h-4 w-4 text-indigo-500 dark:text-indigo-400" />
          <h4 className="text-sm font-semibold text-slate-800 dark:text-zinc-200">
            Synthesis Content
          </h4>
        </div>
        <div className="text-sm text-slate-700 dark:text-zinc-300 whitespace-pre-wrap leading-relaxed">
          {content}
        </div>
      </div>
    </div>
  )
}
