'use client'

import { cn } from '@/lib/utils'

export interface PromptPreset {
    id: string
    label: string
    template: string
}

interface PromptPresetsProps {
    onPresetSelected: (template: string) => void
    presets?: PromptPreset[]
}

const DEFAULT_PRESETS: PromptPreset[] = [
    {
        id: 'legal-risk',
        label: 'Legal risk check',
        template: 'Act as a panel of legal experts. Assess the main legal risks and mitigation strategies for: ',
    },
    {
        id: 'pros-cons',
        label: 'Pros & cons',
        template: 'Debate the strongest pros and cons of: ',
    },
    {
        id: 'strategy',
        label: 'Strategy debate',
        template: 'Act as a strategic advisory council. Debate alternative strategies for: ',
    },
    {
        id: 'multi-model',
        label: 'Multi-model comparison',
        template: 'Compare how different AI models would respond to: ',
    },
]

/**
 * PromptPresets - Quick preset chips
 * 
 * Displays clickable preset buttons that append template text to the prompt.
 * Never overwrites existing user text, only appends.
 */
export function PromptPresets({
    onPresetSelected,
    presets = DEFAULT_PRESETS,
}: PromptPresetsProps) {
    return (
        <div className="mx-auto mt-3 flex max-w-2xl flex-wrap gap-2 px-4 sm:px-0">
            {presets.map((preset) => (
                <button
                    key={preset.id}
                    type="button"
                    onClick={() => onPresetSelected(preset.template)}
                    className={cn(
                        'rounded-full border border-brand-border/60 bg-white/70 px-3 py-1 text-xs text-slate-700 transition',
                        'hover:border-brand-accent hover:bg-brand-accent/10'
                    )}
                >
                    {preset.label}
                </button>
            ))}
        </div>
    )
}
