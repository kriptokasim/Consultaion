'use client'

import React from 'react'
import { Loader2, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface PerspectivesReadyActionProps {
  mode: 'arena' | 'debate'
  modelCount?: number
  onContinue: () => void
  isContinuing?: boolean
  outcomeUnknown?: boolean
  className?: string
}

export function PerspectivesReadyAction({
  mode,
  modelCount = 4,
  onContinue,
  isContinuing = false,
  outcomeUnknown = false,
  className,
}: PerspectivesReadyActionProps) {
  return (
    <div className={cn(
      'rounded-2xl border border-amber-200 bg-amber-50/50 p-6 dark:border-amber-900/50 dark:bg-amber-950/20 shadow-md space-y-4 animate-in fade-in duration-200',
      className
    )}>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-amber-500 animate-pulse" />
            {modelCount} perspectives are ready
          </h3>
          <p className="text-sm text-muted-foreground">
            {outcomeUnknown
              ? 'Request was sent but the outcome is unknown. You can safely retry — idempotency will prevent duplicate work.'
              : mode === 'arena'
                ? 'All model responses have been collected. Generate the Decision Report to see consensus, disagreements, and actionable recommendations.'
                : 'Deliberation is complete. Evaluate the arguments and generate the final verdict report.'}
          </p>
        </div>
        <Button
          onClick={onContinue}
          disabled={isContinuing}
          className="bg-amber-600 hover:bg-amber-700 text-white dark:bg-amber-500 dark:hover:bg-amber-600 font-semibold px-6 py-2.5 shadow-sm transition-all rounded-xl shrink-0"
        >
          {outcomeUnknown ? (
            'Retry Synthesis'
          ) : isContinuing ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <Play className="h-4 w-4 mr-2" />
              {mode === 'arena' ? 'Generate Decision Report' : 'Evaluate & Generate Report'}
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
