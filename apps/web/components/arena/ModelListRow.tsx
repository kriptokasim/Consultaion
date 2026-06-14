'use client'

import React from 'react'
import { ShieldAlert, Key, Check } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ModelOption } from './ModelPanelSheet'

interface ModelListRowProps {
  model: ModelOption
  isSelected: boolean
  onToggle: () => void
}

export function ModelListRow({ model, isSelected, onToggle }: ModelListRowProps) {
  return (
    <div
      onClick={onToggle}
      className={cn(
        'border rounded-2xl p-4 cursor-pointer transition-all duration-200 flex flex-col justify-between hover:bg-muted/40 relative',
        isSelected
          ? 'border-primary/60 bg-primary/5 dark:bg-primary/10'
          : 'border-border bg-card'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-sm text-foreground">{model.name}</span>
            <Badge variant="secondary" className="text-[10px] font-semibold py-0 px-1.5 bg-muted">
              {model.capability}
            </Badge>
            {model.byokRequired && (
              <Badge variant="outline" className="text-[10px] font-semibold py-0 px-1.5 border-amber-500/40 text-amber-600 dark:text-amber-400 flex items-center gap-1">
                <Key className="h-2.5 w-2.5" /> BYOK
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground">{model.description}</p>
        </div>

        <div className={cn(
          'h-5 w-5 rounded-full border flex items-center justify-center shrink-0',
          isSelected ? 'border-primary bg-primary text-primary-foreground' : 'border-muted-foreground/30'
        )}>
          {isSelected && <Check className="h-3 w-3 stroke-[3]" />}
        </div>
      </div>

      {model.byokRequired && isSelected && (
        <div className="mt-3 bg-amber-500/10 border border-amber-500/30 rounded-xl p-2.5 text-[10px] text-amber-700 dark:text-amber-400 leading-normal flex items-start gap-2">
          <ShieldAlert className="h-3.5 w-3.5 shrink-0 mt-0.5 text-amber-600" />
          <span>
            This model requires custom key setup (BYOK) enabled in your profile settings.
          </span>
        </div>
      )}
    </div>
  )
}
