'use client'

import { useEffect, useMemo, useState } from 'react'
import { Loader2, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { usePathname, useSearchParams } from 'next/navigation'
import { fetchWithAuth } from '@/lib/auth'

function extractRunId(pathname: string, queryRun: string | null): string | null {
  if (queryRun) return queryRun
  const match = pathname.match(/^\/runs\/([^/]+)$/)
  return match?.[1] ? decodeURIComponent(match[1]) : null
}

export default function StopRunControl() {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const runId = useMemo(() => extractRunId(pathname || '', searchParams.get('run')), [pathname, searchParams])
  const [status, setStatus] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)

  useEffect(() => {
    if (!runId) {
      setStatus(null)
      return
    }

    let cancelled = false
    const load = async () => {
      try {
        const response = await fetchWithAuth(`/debates/${encodeURIComponent(runId)}`)
        if (!response.ok) return
        const data = await response.json()
        if (!cancelled) setStatus(data?.status ?? null)
      } catch {
        // The run workspace owns detailed connection/error UI.
      }
    }
    void load()
    const timer = window.setInterval(load, 3000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [runId])

  const active = status === 'scheduled' || status === 'running' || status === 'perspectives_ready'
  if (!runId || !active) return null

  const stop = async () => {
    if (stopping) return
    setStopping(true)
    try {
      const response = await fetchWithAuth(`/debates/${encodeURIComponent(runId)}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.message || body?.detail || `Stop failed (${response.status})`)
      }
      setStatus('cancelled')
      window.dispatchEvent(new CustomEvent('consultaion:run-cancelled', { detail: { id: runId } }))
    } catch (error) {
      console.error('[StopRunControl] cancellation failed', error)
    } finally {
      setStopping(false)
    }
  }

  return (
    <div className="fixed bottom-[calc(var(--mobile-bottom-nav-height)+1rem)] right-4 z-50 sm:bottom-5 sm:right-6">
      <Button
        type="button"
        variant="outline"
        onClick={stop}
        disabled={stopping}
        aria-label="Stop Run"
        className="rounded-full border-red-300 bg-white/95 px-4 text-red-700 shadow-lg backdrop-blur hover:bg-red-50 dark:border-red-800 dark:bg-stone-900/95 dark:text-red-300 dark:hover:bg-red-950/40"
      >
        {stopping ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Square className="mr-2 h-3.5 w-3.5 fill-current" />}
        {stopping ? 'Stopping…' : 'Stop Run'}
      </Button>
    </div>
  )
}
