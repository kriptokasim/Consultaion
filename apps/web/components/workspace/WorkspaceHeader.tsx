'use client'

import React from 'react'
import Link from 'next/link'
import { ArrowLeft, Settings } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { WorkspaceStage } from '@/lib/workspace/types'

interface WorkspaceHeaderProps {
  stage: WorkspaceStage
  prompt?: string
  mode?: 'arena' | 'debate'
  modelCount?: number
  onBack?: () => void
  onSettings?: () => void
  className?: string
}

const STAGE_LABELS: Record<WorkspaceStage, string> = {
  idle: 'New Decision',
  creating: 'Starting...',
  contacting_models: 'Contacting Models',
  collecting_perspectives: 'Collecting Perspectives',
  perspectives_ready: 'Perspectives Ready',
  scoring: 'Evaluating',
  analyzing_divergence: 'Analyzing Divergence',
  synthesizing: 'Synthesizing Report',
  verifying: 'Verifying',
  complete: 'Complete',
  degraded: 'Degraded',
  failed: 'Failed',
}

export function WorkspaceHeader({
  stage,
  prompt,
  mode = 'arena',
  modelCount = 4,
  onBack,
  onSettings,
  className,
}: WorkspaceHeaderProps) {
  return (
    <header className={cn(
      'flex items-center justify-between gap-3 px-4 py-2 border-b border-border bg-background/90 backdrop-blur-sm sticky top-0 z-30',
      className
    )}>
      <div className="flex items-center gap-2 min-w-0">
        {onBack ? (
          <button
            onClick={onBack}
            className="inline-flex items-center justify-center h-11 w-11 rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted/50 transition shrink-0"
            aria-label="Go back"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
        ) : (
          <Link
            href="/live"
            className="inline-flex items-center justify-center h-11 w-11 rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted/50 transition shrink-0"
            aria-label="Go back to Arena"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
        )}
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-semibold text-foreground capitalize">{mode}</span>
          </div>
          {prompt && (
            <p className="text-xs text-muted-foreground truncate max-w-[200px] sm:max-w-[400px]">
              {prompt}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {stage !== 'idle' && stage !== 'creating' && (
          <span className={cn(
            'text-xs font-medium px-2.5 py-1 rounded-full',
            stage === 'complete' && 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
            stage === 'failed' && 'bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-300',
            stage === 'perspectives_ready' && 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
            !['complete', 'failed', 'perspectives_ready'].includes(stage) && 'bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300',
          )}>
            {STAGE_LABELS[stage]}
          </span>
        )}
        {onSettings && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onSettings}
            className="h-11 w-11 rounded-xl"
            aria-label="Settings"
          >
            <Settings className="h-5 w-5" />
          </Button>
        )}
      </div>
    </header>
  )
}
