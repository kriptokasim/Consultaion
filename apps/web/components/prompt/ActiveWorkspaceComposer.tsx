'use client'

import React, { useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ActiveWorkspaceComposerProps {
  value: string
  onChange: (val: string) => void
  onSubmit: () => void
  placeholder?: string
  isLoading?: boolean
  disabled?: boolean
  className?: string
}

export function ActiveWorkspaceComposer({
  value,
  onChange,
  onSubmit,
  placeholder = 'Ask a follow-up or refine the decision report...',
  isLoading = false,
  disabled = false,
  className,
}: ActiveWorkspaceComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-grow textarea height
  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    textarea.style.height = 'auto'
    const newHeight = Math.min(Math.max(textarea.scrollHeight, 40), 120)
    textarea.style.height = `${newHeight}px`
  }, [value])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (value.trim().length > 0 && !disabled && !isLoading) {
        onSubmit()
      }
    }
  }

  return (
    <div
      className={cn(
        'fixed bottom-0 left-0 right-0 z-40 bg-background/80 backdrop-blur-md border-t border-border px-4 py-3 pb-[calc(12px+env(safe-area-inset-bottom))] shadow-[0_-8px_32px_rgba(0,0,0,0.05)] transition-all',
        className
      )}
    >
      <div className="max-w-4xl mx-auto flex items-end gap-3">
        <div className="flex-1 bg-muted/50 hover:bg-muted/80 focus-within:bg-card border border-border/80 focus-within:border-primary/40 focus-within:ring-2 focus-within:ring-primary/10 rounded-2xl px-3 py-1.5 transition-all flex items-end">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled || isLoading}
            placeholder={placeholder}
            rows={1}
            style={{ fontSize: '16px' }} // prevent iOS auto-zoom
            className="w-full bg-transparent text-foreground placeholder:text-muted-foreground outline-none resize-none min-h-[40px] max-h-[120px] py-1 leading-relaxed custom-scrollbar"
          />
        </div>
        <Button
          size="icon"
          onClick={onSubmit}
          disabled={disabled || isLoading || !value.trim()}
          className="h-11 w-11 rounded-2xl shrink-0 bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm"
        >
          <Send className="h-4.5 w-4.5" />
        </Button>
      </div>
    </div>
  )
}
