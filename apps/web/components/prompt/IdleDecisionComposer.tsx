'use client'

import React, { useRef, useEffect, useState } from 'react'
import { Scale, Sparkles } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { usePromptHistory } from '@/hooks/usePromptHistory'
import { useI18n } from '@/lib/i18n/client'
import { useVisualViewport } from '@/hooks/useVisualViewport'

export type RunPhase = 'idle' | 'creating' | 'active' | 'synthesizing' | 'completed' | 'failed' | 'cancelled'

interface IdleDecisionComposerProps {
  value: string
  onChange: (val: string) => void
  onSubmit: () => void
  mode: 'arena' | 'debate'
  onModeChange: (mode: 'arena' | 'debate') => void
  placeholder?: string
  isLoading?: boolean
  disabled?: boolean
  onConfigureModels?: () => void
  runPhase?: RunPhase
  onNewRun?: () => void
}

export function IdleDecisionComposer({
  value,
  onChange,
  onSubmit,
  mode,
  onModeChange,
  placeholder,
  isLoading = false,
  disabled = false,
  onConfigureModels,
  runPhase = 'idle',
  onNewRun,
}: IdleDecisionComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { history, addToHistory } = usePromptHistory()
  const { t } = useI18n()
  const { isKeyboardOpen, keyboardInset } = useVisualViewport()
  const [showHistory, setShowHistory] = useState(false)

  // Auto-grow textarea logic
  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    textarea.style.height = 'auto'
    const newHeight = Math.min(Math.max(textarea.scrollHeight, 132), 220)
    textarea.style.height = `${newHeight}px`
  }, [value])

  const handleSubmit = () => {
    if (value.trim().length >= 10) {
      addToHistory(value.trim())
    }
    onSubmit()
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && value.trim().length > 0) {
      e.preventDefault()
      if (!disabled && !isLoading) {
        handleSubmit()
      }
    }
  }

  const selectMode = (nextMode: 'arena' | 'debate') => {
    if (!disabled) {
      onModeChange(nextMode)
    }
  }

  const handleModeKeyDown = (
    event: React.KeyboardEvent<HTMLDivElement>,
    nextMode: 'arena' | 'debate',
  ) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      selectMode(nextMode)
    }
  }

  const defaultPlaceholder =
    mode === 'arena'
      ? t('live.composer.arenaPlaceholder')
      : t('live.composer.debatePlaceholder')

  const primaryActionLabel =
    runPhase === 'creating'
      ? t('live.composer.starting')
      : runPhase === 'active'
        ? t('live.composer.modelsResponding')
        : runPhase === 'synthesizing'
          ? t('live.composer.synthesizing')
          : runPhase === 'completed'
            ? t('live.composer.completed')
            : runPhase === 'failed'
              ? t('live.composer.retry')
              : runPhase === 'cancelled'
                ? t('live.composer.newRun')
                : isLoading
                  ? t('live.composer.launching')
                  : mode === 'arena'
                    ? t('live.composer.launchArena')
                    : t('live.composer.startDebate')

  const primaryActionDisabled =
    disabled ||
    runPhase === 'creating' ||
    runPhase === 'active' ||
    runPhase === 'synthesizing' ||
    runPhase === 'completed' ||
    (runPhase === 'idle' && !value.trim())

  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-8 space-y-6 pb-48 sm:pb-8">
      {/* 1. Mode Cards (Arena & Debate only) — hidden when not idle */}
      {runPhase === 'idle' && (
        <div
          className="grid grid-cols-1 sm:grid-cols-2 gap-4"
          role="radiogroup"
          aria-label={t('live.composer.modeGroupLabel')}
        >
          {/* Arena Card */}
          <Card
            role="radio"
            aria-checked={mode === 'arena'}
            aria-disabled={disabled}
            tabIndex={disabled ? -1 : 0}
            onClick={() => selectMode('arena')}
            onKeyDown={(event) => handleModeKeyDown(event, 'arena')}
            className={cn(
              'min-h-[128px] cursor-pointer p-5 flex flex-col justify-between transition-all duration-300 relative overflow-hidden',
              mode === 'arena'
                ? 'border-amber-500 bg-amber-50/20 dark:bg-amber-950/10 ring-2 ring-amber-500/50'
                : 'border-border/60 hover:border-amber-300 dark:hover:border-amber-900/60'
            )}
          >
            <div className="flex items-start gap-4">
              <div className={cn(
                'p-2.5 rounded-xl transition-colors shrink-0',
                mode === 'arena' ? 'bg-amber-500 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'
              )}>
                <Sparkles className="h-5 w-5" aria-hidden="true" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-base text-foreground flex items-center gap-1.5">
                  {t('live.composer.arenaMode')}
                </h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {t('live.composer.arenaDescription')}
                </p>
              </div>
            </div>
            {mode === 'arena' && (
              <div className="absolute top-2 right-2 h-2 w-2 rounded-full bg-amber-500" aria-hidden="true" />
            )}
          </Card>

          {/* Debate Card */}
          <Card
            role="radio"
            aria-checked={mode === 'debate'}
            aria-disabled={disabled}
            tabIndex={disabled ? -1 : 0}
            onClick={() => selectMode('debate')}
            onKeyDown={(event) => handleModeKeyDown(event, 'debate')}
            className={cn(
              'min-h-[128px] cursor-pointer p-5 flex flex-col justify-between transition-all duration-300 relative overflow-hidden',
              mode === 'debate'
                ? 'border-indigo-500 bg-indigo-50/20 dark:bg-indigo-950/10 ring-2 ring-indigo-500/50'
                : 'border-border/60 hover:border-indigo-300 dark:hover:border-indigo-900/60'
            )}
          >
            <div className="flex items-start gap-4">
              <div className={cn(
                'p-2.5 rounded-xl transition-colors shrink-0',
                mode === 'debate' ? 'bg-indigo-500 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'
              )}>
                <Scale className="h-5 w-5" aria-hidden="true" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-base text-foreground flex items-center gap-1.5">
                  {t('live.composer.debateMode')}
                  <span className="text-[10px] font-bold text-indigo-500/90 bg-indigo-50 dark:bg-indigo-950/60 px-1.5 py-0.5 rounded-md uppercase tracking-wider">
                    {t('live.composer.beta')}
                  </span>
                </h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {t('live.composer.debateDescription')}
                </p>
              </div>
            </div>
            {mode === 'debate' && (
              <div className="absolute top-2 right-2 h-2 w-2 rounded-full bg-indigo-500" aria-hidden="true" />
            )}
          </Card>
        </div>
      )}

      {/* 2. Main Input Box */}
      <div
        className={cn(
          "fixed inset-x-0 bottom-[calc(4rem+var(--keyboard-offset)+env(safe-area-inset-bottom))] sm:bottom-auto z-40 p-3 pb-3 bg-background/80 backdrop-blur-xl border-t border-border/40 shadow-[0_-10px_40px_-15px_rgba(0,0,0,0.1)]",
          "sm:relative sm:z-auto sm:p-4 sm:pb-4 sm:bg-card/60 sm:border sm:border-border/80 sm:rounded-3xl sm:shadow-smooth-lg sm:backdrop-blur-md"
        )}
        style={{ "--keyboard-offset": `${isKeyboardOpen ? keyboardInset : 0}px` } as React.CSSProperties}
      >
        <div className="w-full max-w-4xl mx-auto relative rounded-2xl sm:rounded-none bg-card sm:bg-transparent p-1 sm:p-0 shadow-sm sm:shadow-none border border-border/40 sm:border-0">
          <div className="relative">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => history.length > 0 && setShowHistory(true)}
              onBlur={() => setTimeout(() => setShowHistory(false), 150)}
              disabled={disabled || isLoading}
              placeholder={placeholder || defaultPlaceholder}
              aria-label={t('live.composer.promptLabel')}
              style={{ fontSize: '16px' }} // Ensures no auto-zoom on iOS
              className={cn(
                'w-full bg-transparent text-foreground placeholder:text-muted-foreground outline-none resize-none',
                'min-h-[132px] max-h-[220px] leading-relaxed custom-scrollbar',
                (disabled || isLoading) && 'cursor-not-allowed opacity-60'
              )}
            />
            {showHistory && history.length > 0 && (
              <div className="absolute left-0 right-0 bottom-full mb-1 sm:bottom-auto sm:top-full sm:mb-0 sm:mt-1 z-50 rounded-2xl border border-border bg-popover shadow-xl overflow-hidden">
                <div className="px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground border-b border-border/50">
                  {t('live.composer.recentPrompts')}
                </div>
                {history.slice(0, 5).map((h, i) => (
                  <button
                    key={i}
                    onMouseDown={(e) => {
                      e.preventDefault()
                      onChange(h)
                      setShowHistory(false)
                    }}
                    className="w-full text-left px-4 py-3 text-sm text-foreground hover:bg-accent transition-colors truncate border-b border-border/30 last:border-0"
                  >
                    {h}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Action Bar */}
          <div className="mt-3 flex items-center justify-between border-t border-border/40 pt-3">
            <span className="text-xs text-muted-foreground hidden sm:inline">
              {t('live.composer.shortcutPrefix')}{' '}
              <kbd className="px-1.5 py-0.5 border rounded bg-muted font-sans text-[10px]">⌘/Ctrl + Enter</kbd>{' '}
              {t('live.composer.shortcutSuffix')}
            </span>
            <div className="flex items-center gap-2 ml-auto">
              {onNewRun && (runPhase === 'completed' || runPhase === 'failed' || runPhase === 'cancelled') && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={onNewRun}
                  className="rounded-xl px-4 font-semibold text-sm border-border hover:bg-muted/40"
                >
                  {t('live.composer.newRun')}
                </Button>
              )}
              {onConfigureModels && runPhase === 'idle' && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={onConfigureModels}
                  disabled={disabled || isLoading}
                  className="rounded-xl px-4 font-semibold text-sm border-border hover:bg-muted/40"
                >
                  {t('live.composer.configurePanel')}
                </Button>
              )}
              {runPhase !== 'completed' && runPhase !== 'cancelled' && (
                <Button
                  type="button"
                  onClick={handleSubmit}
                  disabled={primaryActionDisabled}
                  className={cn(
                    'rounded-xl px-5 font-semibold text-sm shadow-sm transition-all',
                    mode === 'arena'
                      ? 'bg-amber-600 hover:bg-amber-700 text-white dark:bg-amber-500 dark:hover:bg-amber-600'
                      : 'bg-indigo-600 hover:bg-indigo-700 text-white dark:bg-indigo-500 dark:hover:bg-indigo-600'
                  )}
                >
                  {primaryActionLabel}
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
