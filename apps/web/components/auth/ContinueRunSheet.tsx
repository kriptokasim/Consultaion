'use client'

import React from 'react'
import { useRouter } from 'next/navigation'
import { ShieldCheck, LogIn, UserPlus } from 'lucide-react'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'

export interface PendingRunIntent {
  id: string
  prompt: string
  models: string[]
  mode: 'arena' | 'debate'
  expiresAt: number
}

interface ContinueRunSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  promptText: string
  selectedModels: string[]
  mode: 'arena' | 'debate'
}

export function ContinueRunSheet({
  open,
  onOpenChange,
  promptText,
  selectedModels,
  mode,
}: ContinueRunSheetProps) {
  const router = useRouter()

  const saveIntentAndRedirect = (targetPath: '/login' | '/register') => {
    const intentId = `intent_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
    const intent: PendingRunIntent = {
      id: intentId,
      prompt: promptText,
      models: selectedModels,
      mode,
      expiresAt: Date.now() + 30 * 60 * 1000, // 30 minutes TTL
    }

    try {
      sessionStorage.setItem(`pending_run_${intentId}`, JSON.stringify(intent))
    } catch (err) {
      console.error('Failed to save pending run intent to sessionStorage:', err)
    }

    // Redirect to login or register with next pointing back to resume flow
    router.push(`${targetPath}?next=${encodeURIComponent(`/live?resume=${intentId}`)}`)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="w-full h-auto max-h-[90dvh] rounded-t-[32px] border-t border-border flex flex-col p-6 bg-background/95 backdrop-blur gap-6 pb-[calc(24px+env(safe-area-inset-bottom))]"
      >
        <SheetHeader className="text-center sm:text-left max-w-xl mx-auto w-full">
          <div className="mx-auto sm:mx-0 h-12 w-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary mb-3">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <SheetTitle className="text-xl font-extrabold tracking-tight">
            Save Your Progress & Run Workspace
          </SheetTitle>
          <SheetDescription className="text-sm text-muted-foreground leading-relaxed">
            Guests are limited to previews. Sign in or create an account to start your workspace comparison run, save history, and export final consensus reports.
          </SheetDescription>
        </SheetHeader>

        <div className="max-w-xl mx-auto w-full flex flex-col sm:flex-row items-center gap-3">
          <Button
            variant="outline"
            className="w-full h-12 rounded-xl flex items-center justify-center gap-2 border-border hover:bg-muted/40 font-semibold"
            onClick={() => saveIntentAndRedirect('/login')}
          >
            <LogIn className="h-4 w-4" />
            Sign In
          </Button>
          <Button
            className="w-full h-12 rounded-xl flex items-center justify-center gap-2 bg-primary text-primary-foreground font-semibold"
            onClick={() => saveIntentAndRedirect('/register')}
          >
            <UserPlus className="h-4 w-4" />
            Create Free Account
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
