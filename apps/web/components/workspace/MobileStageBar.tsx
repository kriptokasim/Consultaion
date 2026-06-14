'use client'

import React from 'react'
import { cn } from '@/lib/utils'
import type { WorkspaceStage } from '@/lib/workspace/types'

interface MobileStageBarProps {
  currentStage: WorkspaceStage
  responsesReceived?: number
  modelsExpected?: number
  elapsedSeconds?: number
  onToggleDetails?: () => void
  showDetails?: boolean
  className?: string
}

const STAGE_ORDER: WorkspaceStage[] = [
  'creating',
  'contacting_models',
  'collecting_perspectives',
  'scoring',
  'analyzing_divergence',
  'synthesizing',
  'verifying',
  'complete',
]

export function MobileStageBar({
  currentStage,
  responsesReceived = 0,
  modelsExpected = 4,
  elapsedSeconds = 0,
  onToggleDetails,
  showDetails = false,
  className,
}: MobileStageBarProps) {
  const activeIdx = STAGE_ORDER.indexOf(currentStage)
  const progress = activeIdx >= 0 ? activeIdx / (STAGE_ORDER.length - 1) : 0

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className={cn(
      'rounded-2xl border border-border bg-card p-3 shadow-sm',
      className
    )}>
      {/* Compact bar */}
      <button
        onClick={onToggleDetails}
        className="w-full flex items-center justify-between text-xs cursor-pointer"
        aria-expanded={showDetails}
        aria-label={`Pipeline progress: ${currentStage.replace(/_/g, ' ')}`}
      >
        <div className="flex items-center gap-2">
          <div className="relative h-1.5 w-24 bg-muted rounded-full overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 bg-primary rounded-full transition-all duration-500"
              style={{ width: `${Math.max(progress * 100, 5)}%` }}
            />
          </div>
          <span className="font-medium text-foreground">
            {currentStage === 'collecting_perspectives'
              ? `Perspectives ${responsesReceived}/${modelsExpected}`
              : currentStage.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
          </span>
        </div>
        <div className="flex items-center gap-2 text-muted-foreground">
          <span className="font-mono">{formatTime(elapsedSeconds)}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted">
            {showDetails ? 'Hide' : 'Details'}
          </span>
        </div>
      </button>

      {/* Expanded details */}
      {showDetails && (
        <div className="mt-3 pt-3 border-t border-border/60 space-y-1.5">
          {STAGE_ORDER.map((stage, idx) => {
            const isDone = activeIdx >= 0 && idx < activeIdx
            const isActive = stage === currentStage
            const isPending = activeIdx >= 0 && idx > activeIdx || activeIdx < 0

            return (
              <div
                key={stage}
                className={cn(
                  'flex items-center gap-2 text-xs',
                  isDone && 'text-emerald-600 dark:text-emerald-400',
                  isActive && 'text-primary font-medium',
                  isPending && 'text-muted-foreground',
                )}
              >
                <div className={cn(
                  'h-1.5 w-1.5 rounded-full shrink-0',
                  isDone && 'bg-emerald-500',
                  isActive && 'bg-primary animate-pulse',
                  isPending && 'bg-muted-foreground/30',
                )} />
                <span className="capitalize">{stage.replace(/_/g, ' ')}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
