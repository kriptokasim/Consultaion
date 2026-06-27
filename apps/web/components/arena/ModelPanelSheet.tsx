'use client'

import React, { useState, useMemo, useEffect } from 'react'
import { ShieldAlert } from 'lucide-react'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { ModelSearchInput } from './ModelSearchInput'
import { SelectedModelsTray } from './SelectedModelsTray'
import { ModelListRow } from './ModelListRow'

export interface ModelOption {
  id: string
  name: string
  provider: string
  providerKey: string
  capability: 'Fast' | 'Deep Reasoning' | 'Multimodal' | 'General'
  description: string
  byokRequired?: boolean
  estimatedCost?: string
}

export const AVAILABLE_MODELS: ModelOption[] = [
  {
    id: 'gpt-4o-mini',
    name: 'GPT-4o Mini',
    provider: 'OpenAI',
    providerKey: 'openai',
    capability: 'Fast',
    description: 'Fast, lightweight model optimal for quick checks and high-throughput tasks.',
    estimatedCost: '$0.15 / 1M tokens',
  },
  {
    id: 'gpt-4o',
    name: 'GPT-4o',
    provider: 'OpenAI',
    providerKey: 'openai',
    capability: 'General',
    description: 'Standard flagship model with high accuracy across reasoning and structuring.',
    estimatedCost: '$5.00 / 1M tokens',
  },
  {
    id: 'claude-3-5-sonnet',
    name: 'Claude 3.5 Sonnet',
    provider: 'Anthropic',
    providerKey: 'anthropic',
    capability: 'Deep Reasoning',
    description: 'State-of-the-art reasoning, excellent for critical debates and complex analysis.',
    estimatedCost: '$3.00 / 1M tokens',
  },
  {
    id: 'claude-3-5-haiku',
    name: 'Claude 3.5 Haiku',
    provider: 'Anthropic',
    providerKey: 'anthropic',
    capability: 'Fast',
    description: 'Highly responsive model designed for speed and structured instructions.',
    estimatedCost: '$0.25 / 1M tokens',
  },
  {
    id: 'gemini-1.5-flash',
    name: 'Gemini 1.5 Flash',
    provider: 'Google',
    providerKey: 'google',
    capability: 'Multimodal',
    description: 'Google’s highly efficient multimodal engine with a large context window.',
    estimatedCost: '$0.35 / 1M tokens',
  },
  {
    id: 'gemini-1.5-pro',
    name: 'Gemini 1.5 Pro',
    provider: 'Google',
    providerKey: 'google',
    capability: 'Deep Reasoning',
    description: 'Excellent analytical skills, perfect for code review and broad context synthesis.',
    byokRequired: true, // Example BYOK model
    estimatedCost: '$3.50 / 1M tokens',
  },
]

interface ModelPanelSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  selectedModelIds: string[]
  onSave: (selectedIds: string[]) => void
}

export function ModelPanelSheet({
  open,
  onOpenChange,
  selectedModelIds,
  onSave,
}: ModelPanelSheetProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [tempSelection, setTempSelection] = useState<string[]>(selectedModelIds)

  // Sync temp state when panel opens
  useEffect(() => {
    if (open) {
      setTempSelection(selectedModelIds)
      document.body.style.overflow = 'hidden'
      document.body.style.overscrollBehavior = 'contain'
    } else {
      document.body.style.overflow = ''
      document.body.style.overscrollBehavior = ''
    }
    return () => {
      document.body.style.overflow = ''
      document.body.style.overscrollBehavior = ''
    }
  }, [open, selectedModelIds])

  const filteredModels = useMemo(() => {
    return AVAILABLE_MODELS.filter(
      (m) =>
        m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.provider.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.capability.toLowerCase().includes(searchQuery.toLowerCase())
    )
  }, [searchQuery])

  const toggleModel = (id: string) => {
    setTempSelection((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    )
  }

  const isValid = tempSelection.length >= 2
  const hasByokSelected = tempSelection.some((id) => AVAILABLE_MODELS.find((m) => m.id === id)?.byokRequired)

  const handleApply = () => {
    if (isValid) {
      onSave(tempSelection)
      onOpenChange(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-md h-[92dvh] sm:h-full bottom-0 top-auto sm:top-0 border-t sm:border-l flex flex-col p-0 bg-background/95 backdrop-blur"
      >
        <SheetHeader className="p-6 pb-4 border-b border-border/40">
          <SheetTitle className="text-xl font-bold">Select AI Panel Models</SheetTitle>
          <SheetDescription>
            Choose at least 2 models to participate in the perspective comparison.
          </SheetDescription>
        </SheetHeader>

        {/* Search Input (16px font to prevent iOS zoom) */}
        <ModelSearchInput value={searchQuery} onChange={setSearchQuery} />

        {/* Selected Models Tray */}
        <SelectedModelsTray selectedIds={tempSelection} onRemove={(id) => setTempSelection((prev) => prev.filter((item) => item !== id))} />

        {/* Scrollable Model List */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 custom-scrollbar">
          {filteredModels.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No models match your search.</p>
          ) : (
            filteredModels.map((model) => (
              <ModelListRow
                key={model.id}
                model={model}
                isSelected={tempSelection.includes(model.id)}
                onToggle={() => toggleModel(model.id)}
              />
            ))
          )}
        </div>

        {/* Validation & Save Footer */}
        <div className="p-6 border-t border-border/40 bg-card/65 space-y-4">
          {!isValid && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 text-xs text-red-600 dark:text-red-400 leading-relaxed flex items-start gap-2">
              <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
              <span>You must select at least 2 models to perform a comparison run.</span>
            </div>
          )}

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              className="flex-1 rounded-xl"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              className="flex-1 rounded-xl bg-primary text-primary-foreground font-semibold"
              disabled={!isValid}
              onClick={handleApply}
            >
              Apply Selection ({tempSelection.length})
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
