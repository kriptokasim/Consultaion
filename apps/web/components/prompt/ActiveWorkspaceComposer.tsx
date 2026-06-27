'use client'

import React, { useRef, useEffect, useState } from 'react'
import { Send, Keyboard } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Drawer } from 'vaul'

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
  const textareaRefDesktop = useRef<HTMLTextAreaElement>(null)
  const textareaRefMobile = useRef<HTMLTextAreaElement>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Auto-grow textarea height for desktop
  useEffect(() => {
    const textarea = textareaRefDesktop.current
    if (!textarea) return

    textarea.style.height = 'auto'
    const newHeight = Math.min(Math.max(textarea.scrollHeight, 40), 120)
    textarea.style.height = `${newHeight}px`
  }, [value])

  // Auto-grow textarea height for mobile
  useEffect(() => {
    const textarea = textareaRefMobile.current
    if (!textarea) return

    textarea.style.height = 'auto'
    const newHeight = Math.min(Math.max(textarea.scrollHeight, 40), 120)
    textarea.style.height = `${newHeight}px`
  }, [value, drawerOpen])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>, isMobile: boolean) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (value.trim().length > 0 && !disabled && !isLoading) {
        if (isMobile) {
          setDrawerOpen(false)
        }
        onSubmit()
      }
    }
  }

  const handleMobileSubmit = () => {
    if (value.trim().length > 0 && !disabled && !isLoading) {
      setDrawerOpen(false)
      onSubmit()
    }
  }

  return (
    <div
      className={cn(
        'fixed bottom-16 sm:bottom-0 left-0 right-0 z-40 bg-background/80 backdrop-blur-md border-t border-border px-4 py-3 pb-[calc(12px+env(safe-area-inset-bottom))] sm:pb-3 shadow-[0_-8px_32px_#0000000d] transition-all',
        className
      )}
    >
      {/* Desktop Input */}
      <div className="hidden sm:flex max-w-4xl mx-auto items-end gap-3">
        <div className="flex-1 bg-muted/50 hover:bg-muted/80 focus-within:bg-card border border-border/80 focus-within:border-primary/40 focus-within:ring-2 focus-within:ring-primary/10 rounded-2xl px-3 py-1.5 transition-all flex items-end">
          <textarea
            ref={textareaRefDesktop}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => handleKeyDown(e, false)}
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

      {/* Mobile Drawer Trigger & Dummy Input */}
      <div className="flex sm:hidden max-w-4xl mx-auto items-center gap-3">
        <Drawer.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
          <Drawer.Trigger asChild>
            <div className="flex-1 bg-muted/50 border border-border/80 rounded-2xl px-4 py-3 flex items-center gap-3 text-muted-foreground cursor-pointer shadow-sm">
              <Keyboard className="h-5 w-5 opacity-50" />
              <span className="truncate text-[15px]">{value || placeholder}</span>
            </div>
          </Drawer.Trigger>
          <Drawer.Portal>
            <Drawer.Overlay className="fixed inset-0 bg-black/40 z-50" />
            <Drawer.Content className="bg-background flex flex-col rounded-t-[20px] h-[50vh] mt-24 fixed bottom-0 left-0 right-0 z-50 outline-none">
              <div className="p-4 bg-background rounded-t-[20px] flex-1 flex flex-col">
                <div className="mx-auto w-12 h-1.5 flex-shrink-0 rounded-full bg-muted mb-6" />
                <div className="flex-1 bg-muted/30 focus-within:bg-card border border-border/50 focus-within:border-primary/40 focus-within:ring-2 focus-within:ring-primary/10 rounded-2xl px-3 py-2 transition-all flex items-start overflow-hidden shadow-inner">
                  <textarea
                    ref={textareaRefMobile}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    onKeyDown={(e) => handleKeyDown(e, true)}
                    disabled={disabled || isLoading}
                    placeholder={placeholder}
                    autoFocus
                    style={{ fontSize: '16px' }} // prevent iOS auto-zoom
                    className="w-full h-full bg-transparent text-foreground placeholder:text-muted-foreground outline-none resize-none py-1 leading-relaxed custom-scrollbar"
                  />
                </div>
                <div className="mt-4 flex justify-end">
                  <Button
                    size="lg"
                    onClick={handleMobileSubmit}
                    disabled={disabled || isLoading || !value.trim()}
                    className="rounded-full bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm px-8"
                  >
                    <Send className="h-5 w-5 mr-2" />
                    Send
                  </Button>
                </div>
              </div>
            </Drawer.Content>
          </Drawer.Portal>
        </Drawer.Root>
      </div>
    </div>
  )
}
