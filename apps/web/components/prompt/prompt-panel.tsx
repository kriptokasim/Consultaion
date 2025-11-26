'use client'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { KeyboardEvent } from 'react'

export type PromptPanelStatus = 'idle' | 'running' | 'error'

interface PromptPanelProps {
    value: string
    onChange: (value: string) => void
    onSubmit: () => void
    status?: PromptPanelStatus
    disabled?: boolean
    helperText?: string
    submitLabel?: string
    isSubmitLoading?: boolean
    onAdvancedSettingsClick?: () => void
}

/**
 * PromptPanel - Central prompt surface component
 * 
 * A focused, modern prompt input area with:
 * - Multiline textarea
 * - Enter to submit (Shift+Enter for newline)
 * - Status indicators (idle, running, error)
 * - Optional advanced settings trigger
 */
export function PromptPanel({
    value,
    onChange,
    onSubmit,
    status = 'idle',
    disabled = false,
    helperText = 'Describe what you want the AI Parliament to debate…',
    submitLabel = 'Start debate',
    isSubmitLoading = false,
    onAdvancedSettingsClick,
}: PromptPanelProps) {
    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        // Enter submits (without Shift), Shift+Enter adds newline
        if (e.key === 'Enter' && !e.shiftKey && value.trim().length > 0) {
            e.preventDefault()
            if (!disabled && status !== 'running') {
                onSubmit()
            }
        }
    }

    const canSubmit = value.trim().length > 0 && !disabled && status !== 'running'

    return (
        <div className="mx-auto w-full max-w-2xl px-4 sm:px-0">
            <div
                className={cn(
                    'rounded-3xl border bg-white/80 p-4 shadow-sm backdrop-blur-sm transition-all duration-200 sm:p-6',
                    status === 'running' && 'opacity-95',
                    status === 'error' ? 'border-red-300' : 'border-brand-border/60'
                )}
            >
                {/* Running status badge */}
                {status === 'running' && (
                    <div className="mb-3 flex items-center justify-end">
                        <span className="inline-flex items-center gap-2 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">
                            <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
                            Debate in progress…
                        </span>
                    </div>
                )}

                {/* Textarea */}
                <textarea
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={disabled || status === 'running'}
                    placeholder="What should the AI Parliament debate?"
                    className={cn(
                        'w-full resize-none bg-transparent text-sm outline-none placeholder:text-slate-400 sm:text-base',
                        'min-h-[120px] text-slate-900 sm:min-h-[160px]',
                        (disabled || status === 'running') && 'cursor-not-allowed opacity-60'
                    )}
                />

                {/* Error message */}
                {status === 'error' && (
                    <p className="mt-2 text-sm text-red-600">
                        Failed to start debate. Please try again.
                    </p>
                )}

                {/* Footer row */}
                <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                    {/* Helper text */}
                    <p className="text-xs text-slate-500">{helperText}</p>

                    {/* Right side controls */}
                    <div className="flex items-center gap-2">
                        {/* Advanced settings trigger */}
                        {onAdvancedSettingsClick && (
                            <button
                                type="button"
                                className="text-xs text-slate-500 underline-offset-2 transition hover:text-slate-700 hover:underline"
                                onClick={onAdvancedSettingsClick}
                            >
                                Advanced settings
                            </button>
                        )}

                        {/* Submit button */}
                        <Button
                            type="button"
                            size="sm"
                            disabled={!canSubmit}
                            onClick={onSubmit}
                            className="bg-brand-accent text-white hover:bg-brand-accent/90"
                        >
                            {isSubmitLoading || status === 'running' ? 'Running…' : submitLabel}
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    )
}
