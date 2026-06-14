'use client'

import React from 'react'
import { Bot, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { WorkspaceModelSlot } from '@/lib/workspace/types'

interface PerspectivesGridProps {
  modelSlots: WorkspaceModelSlot[]
  className?: string
}

function ModelSlotCard({ slot, index }: { slot: WorkspaceModelSlot; index: number }) {
  const stateColors: Record<string, string> = {
    queued: 'border-border bg-card',
    connecting: 'border-blue-200 bg-blue-50/30 dark:border-blue-900/50 dark:bg-blue-950/20',
    streaming: 'border-amber-200 bg-amber-50/30 dark:border-amber-900/50 dark:bg-amber-950/20',
    complete: 'border-emerald-200 bg-emerald-50/30 dark:border-emerald-900/50 dark:bg-emerald-950/20',
    failed: 'border-red-200 bg-red-50/30 dark:border-red-900/50 dark:bg-red-950/20',
  }

  return (
    <div
      className={cn(
        'rounded-2xl border p-4 transition-all duration-300 min-h-[140px]',
        stateColors[slot.state] || stateColors.queued
      )}
      aria-label={`${slot.display_name}: ${slot.state}`}
      aria-busy={slot.state === 'streaming' || slot.state === 'connecting'}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground truncate">{slot.display_name}</p>
          <p className="text-xs text-muted-foreground">{slot.provider}</p>
        </div>
        <div className="shrink-0">
          {slot.state === 'complete' && (
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          )}
          {slot.state === 'failed' && (
            <AlertCircle className="h-4 w-4 text-red-500" />
          )}
          {(slot.state === 'connecting' || slot.state === 'streaming') && (
            <Loader2 className="h-4 w-4 text-primary animate-spin" />
          )}
          {slot.state === 'queued' && (
            <Bot className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </div>

      {/* Skeleton placeholder for streaming state */}
      {slot.state === 'connecting' && (
        <div className="space-y-2">
          <div className="h-3 bg-muted rounded-full w-full animate-pulse" />
          <div className="h-3 bg-muted rounded-full w-4/5 animate-pulse" />
          <div className="h-3 bg-muted rounded-full w-3/5 animate-pulse" />
        </div>
      )}

      {/* Content preview for complete state */}
      {slot.state === 'complete' && slot.content && (
        <p className="text-xs text-muted-foreground line-clamp-4 leading-relaxed">
          {slot.content.slice(0, 200)}
          {slot.content.length > 200 ? '...' : ''}
        </p>
      )}

      {/* Skeleton for queued */}
      {slot.state === 'queued' && (
        <div className="space-y-2 mt-2">
          <div className="h-2.5 bg-muted/60 rounded-full w-full" />
          <div className="h-2.5 bg-muted/60 rounded-full w-3/4" />
        </div>
      )}
    </div>
  )
}

export function PerspectivesGrid({ modelSlots, className }: PerspectivesGridProps) {
  return (
    <div className={cn('space-y-3', className)}>
      <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
        <Bot className="h-4 w-4" />
        Model Perspectives
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {modelSlots.map((slot, i) => (
          <ModelSlotCard key={slot.model_id || i} slot={slot} index={i} />
        ))}
      </div>
    </div>
  )
}
