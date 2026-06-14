'use client'

import React from 'react'
import { X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { AVAILABLE_MODELS, type ModelOption } from './ModelPanelSheet'

interface SelectedModelsTrayProps {
  selectedIds: string[]
  onRemove: (id: string) => void
}

export function SelectedModelsTray({ selectedIds, onRemove }: SelectedModelsTrayProps) {
  if (selectedIds.length === 0) return null

  return (
    <div className="px-6 py-3 border-b border-border/40 bg-muted/20">
      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2">
        Selected ({selectedIds.length})
      </p>
      <div className="flex flex-wrap gap-1.5">
        {selectedIds.map((id) => {
          const model = AVAILABLE_MODELS.find((m) => m.id === id)
          if (!model) return null
          return (
            <Badge
              key={id}
              variant="secondary"
              className="text-xs font-medium py-1 px-2 gap-1 cursor-pointer hover:bg-destructive/10 transition-colors"
              onClick={() => onRemove(id)}
            >
              {model.name}
              <X className="h-3 w-3" />
            </Badge>
          )
        })}
      </div>
    </div>
  )
}
