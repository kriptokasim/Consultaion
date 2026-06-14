'use client'

import React from 'react'
import { Check, Loader2, Circle, Pause } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { WorkspaceStage } from '@/lib/workspace/types'

interface DesktopStageRailProps {
  currentStage: WorkspaceStage
  elapsedSeconds?: number
  className?: string
}

const RAIL_STAGES: { key: WorkspaceStage; label: string }[] = [
  { key: 'contacting_models', label: 'Models contacted' },
  { key: 'collecting_perspectives', label: 'Collecting perspectives' },
  { key: 'perspectives_ready', label: 'Perspectives ready' },
  { key: 'scoring', label: 'Evaluating responses' },
  { key: 'analyzing_divergence', label: 'Analyzing divergence' },
  { key: 'synthesizing', label: 'Synthesizing report' },
  { key: 'verifying', label: 'Verifying report' },
  { key: 'complete', label: 'Complete' },
]

function getRailIndex(stage: WorkspaceStage): number {
  return RAIL_STAGES.findIndex((s) => s.key === stage)
}

export function DesktopStageRail({
  currentStage,
  elapsedSeconds = 0,
  className,
}: DesktopStageRailProps) {
  const activeIdx = getRailIndex(currentStage)

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className={cn(
      'rounded-2xl border border-border bg-card p-4 shadow-sm',
      className
    )}>
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Pipeline Progress
        </p>
        <span className="text-xs font-mono text-muted-foreground">
          {formatTime(elapsedSeconds)}
        </span>
      </div>
      <div className="space-y-2">
        {RAIL_STAGES.map((stage, idx) => {
          const isDone = activeIdx >= 0 && idx < activeIdx
          const isActive = stage.key === currentStage

          return (
            <div
              key={stage.key}
              className={cn(
                'flex items-center gap-2.5 text-sm transition-colors',
                isDone && 'text-emerald-600 dark:text-emerald-400',
                isActive && 'text-primary font-medium',
                !isDone && !isActive && 'text-muted-foreground',
              )}
            >
              {isDone ? (
                <Check className="h-4 w-4 shrink-0" />
              ) : isActive ? (
                currentStage === 'perspectives_ready' ? (
                  <Pause className="h-4 w-4 text-amber-500 shrink-0 animate-pulse" />
                ) : (
                  <Loader2 className="h-4 w-4 text-primary shrink-0 animate-spin" />
                )
              ) : (
                <Circle className="h-4 w-4 shrink-0" />
              )}
              <span>{stage.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
