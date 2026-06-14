'use client'

import React, { useState, useMemo, useEffect } from 'react'
import { Search, ShieldAlert, Key, Check } from 'lucide-react'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export interface ModelOption {
  id: string
  name: string
  provider: string
  providerKey: string
  capability: 'Fast' | 'Deep Reasoning' | 'Multimodal' | 'General'
  description: string
  byokRequired?: boolean
}

export const AVAILABLE_MODELS: ModelOption[] = [
  {
    id: 'gpt-4o-mini',
    name: 'GPT-4o Mini',
    provider: 'OpenAI',
    providerKey: 'openai',
    capability: 'Fast',
    description: 'Fast, lightweight model optimal for quick checks and high-throughput tasks.',
  },
  {
    id: 'gpt-4o',
    name: 'GPT-4o',
    provider: 'OpenAI',
    providerKey: 'openai',
    capability: 'General',
    description: 'Standard flagship model with high accuracy across reasoning and structuring.',
  },
  {
    id: 'claude-3-5-sonnet',
    name: 'Claude 3.5 Sonnet',
    provider: 'Anthropic',
    providerKey: 'anthropic',
    capability: 'Deep Reasoning',
    description: 'State-of-the-art reasoning, excellent for critical debates and complex analysis.',
  },
  {
    id: 'claude-3-5-haiku',
    name: 'Claude 3.5 Haiku',
    provider: 'Anthropic',
    providerKey: 'anthropic',
    capability: 'Fast',
    description: 'Highly responsive model designed for speed and structured instructions.',
  },
  {
    id: 'gemini-1.5-flash',
    name: 'Gemini 1.5 Flash',
    provider: 'Google',
    providerKey: 'google',
    capability: 'Multimodal',
    description: 'Google’s highly efficient multimodal engine with a large context window.',
  },
  {
    id: 'gemini-1.5-pro',
    name: 'Gemini 1.5 Pro',
    provider: 'Google',
    providerKey: 'google',
    capability: 'Deep Reasoning',
    description: 'Excellent analytical skills, perfect for code review and broad context synthesis.',
    byokRequired: true, // Example BYOK model
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
        <div className="px-6 py-3 border-b border-border/40 bg-muted/30 flex items-center gap-2">
          <Search className="h-4 w-4 text-muted-foreground shrink-0" />
          <input
            type="text"
            placeholder="Search models or providers..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ fontSize: '16px' }}
            className="w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none py-1"
          />
        </div>

        {/* Scrollable Model List */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 custom-scrollbar">
          {filteredModels.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No models match your search.</p>
          ) : (
            filteredModels.map((model) => {
              const isSelected = tempSelection.includes(model.id)
              return (
                <div
                  key={model.id}
                  onClick={() => toggleModel(model.id)}
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
            })
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
