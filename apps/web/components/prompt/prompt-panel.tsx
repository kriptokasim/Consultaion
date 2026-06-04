'use client'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { KeyboardEvent } from 'react'
import { Scale, MessageCircle } from 'lucide-react'

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
    mode?: 'arena' | 'debate' | 'conversation'
    onModeChange?: (mode: 'arena' | 'debate' | 'conversation') => void
    autoFocus?: boolean
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
    helperText = 'Describe what you want the AI Arena to run…',
    submitLabel = 'Run Arena',
    isSubmitLoading = false,
    onAdvancedSettingsClick,
    mode = 'arena',
    onModeChange,
    autoFocus = false,
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
        <div className="mx-auto w-full max-w-3xl px-4 sm:px-0">
            <div
                className={cn(
                    'rounded-3xl border bg-white/80 p-5 shadow-smooth-lg backdrop-blur-sm transition-all duration-200 sm:p-7',
                    status === 'running' && 'opacity-95',
                    status === 'error' ? 'border-red-300' : 'border-brand-border/60'
                )}
            >
                {/* Header: Mode Toggle or Status */}
                <div className="mb-4 flex items-center justify-between">
                    {onModeChange && status !== 'running' ? (
                        <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1">
                            <button
                                type="button"
                                onClick={() => onModeChange('arena')}
                                className={cn(
                                    "flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold transition-all",
                                    mode === 'arena'
                                        ? "bg-white shadow-sm text-slate-900 font-bold ring-1 ring-black/5"
                                        : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
                                )}
                            >
                                <Scale className="h-3.5 w-3.5 text-amber-500" />
                                Arena
                            </button>
                            <button
                                type="button"
                                onClick={() => onModeChange('debate')}
                                className={cn(
                                    "flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold transition-all",
                                    mode === 'debate'
                                        ? "bg-white shadow-sm text-slate-900 font-bold ring-1 ring-black/5"
                                        : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
                                )}
                            >
                                <Scale className="h-3.5 w-3.5 text-indigo-500" />
                                Debate
                            </button>
                            <button
                                type="button"
                                onClick={() => onModeChange('conversation')}
                                className={cn(
                                    "flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold transition-all",
                                    mode === 'conversation'
                                        ? "bg-white shadow-sm text-slate-950 font-bold ring-1 ring-indigo-100"
                                        : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
                                )}
                            >
                                <MessageCircle className="h-3.5 w-3.5 text-purple-500" />
                                Conversation
                            </button>
                        </div>
                    ) : <div />}

                    {status === 'running' && (
                        <span className="inline-flex items-center gap-2 rounded-full bg-amber-100 px-3.5 py-1.5 text-xs font-bold text-amber-800">
                            <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
                            {mode === 'conversation' ? 'Conversation in progress…' : mode === 'debate' ? 'Debate in progress…' : 'Arena compare in progress…'}
                        </span>
                    )}
                </div>

                {/* Textarea */}
                <textarea
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={disabled || status === 'running'}
                    autoFocus={autoFocus}
                    placeholder={
                        mode === 'conversation' 
                            ? "What topic should the panel explore collaboratively?" 
                            : mode === 'debate'
                            ? "What should the AI Parliament debate?"
                            : "Ask a question to compare multiple AI models and synthesize the best decision..."
                    }
                    className={cn(
                        'w-full resize-none bg-transparent text-sm outline-none placeholder:text-slate-400 sm:text-base',
                        'min-h-[160px] text-slate-900 sm:min-h-[200px]',
                        (disabled || status === 'running') && 'cursor-not-allowed opacity-60'
                    )}
                />

                {/* Error message */}
                {status === 'error' && (
                    <p className="mt-2 text-sm text-red-600">
                        Failed to start. Please try again.
                    </p>
                )}

                {/* Footer row */}
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                    {/* Helper text */}
                    <p className="text-xs text-slate-500">
                        {mode === 'conversation'
                            ? 'Collaborative discussion to synthesize an answer.'
                            : mode === 'debate'
                            ? 'Adversarial debate to find the best argument.'
                            : 'Multi-model compare and synthesis.'}
                    </p>

                    {/* Right side controls */}
                    <div className="flex items-center gap-3">
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
                            size="default"
                            disabled={!canSubmit}
                            onClick={onSubmit}
                            className="bg-brand-accent text-white hover:bg-brand-accent/90 rounded-xl px-5 font-semibold"
                        >
                            {isSubmitLoading || status === 'running' 
                                ? 'Running…' 
                                : (mode === 'conversation' 
                                    ? 'Start Conversation' 
                                    : mode === 'debate' 
                                    ? 'Start Debate' 
                                    : 'Run Arena')}
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    )
}
