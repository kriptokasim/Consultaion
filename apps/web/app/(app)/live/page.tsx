'use client'

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import ParliamentHome from "@/components/parliament/ParliamentHome";
import RateLimitBanner from "@/components/parliament/RateLimitBanner";
import type { Member, ScoreItem } from "@/components/parliament/types";
import type { ArenaRunUiState } from "@/components/parliament/StatusPill";
import { ErrorBanner } from "@/components/ui/error-banner";
import { ApiError, getRateLimitInfo, startDebate, getDebate } from "@/lib/api";
import { defaultPanelConfig, type PanelSeatConfig } from "@/lib/panels";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { getMe } from "@/lib/auth";
import { useI18n } from "@/lib/i18n/client";
import { PromptPresets, AdvancedSettingsDrawer, IdleDecisionComposer } from "@/components/prompt";
import { ModelPanelSheet, AVAILABLE_MODELS } from "@/components/arena/ModelPanelSheet";
import { ContinueRunSheet } from "@/components/auth/ContinueRunSheet";
import { track } from "@/lib/analytics";
import { useDebatesList } from "@/lib/api/hooks/useDebatesList";
import { DashboardRunsHistory } from "@/components/dashboard/DashboardRunsHistory";
import { normalizeApiError, type ClientError, shouldRedirectToLogin } from "@/lib/api/errorContract";
import { type DomainEvent } from "@/lib/api/eventContract";
import { FirstRunGuide } from "@/components/onboarding/FirstRunGuide";

import RunDetailClient from "../runs/[id]/RunDetailClient";
import type { RunSnapshot } from "../runs/[id]/RunDetailClient";

const seatsToMembers = (seats: PanelSeatConfig[]): Member[] =>
  seats.map((seat) => ({
    id: seat.seat_id,
    name: seat.display_name,
    role: seat.role_profile === 'judge' ? 'judge' : seat.role_profile === 'risk_officer' ? 'critic' : 'agent',
    party: seat.provider_key,
  }))

const FALLBACK_MEMBERS: Member[] = seatsToMembers(defaultPanelConfig().seats)

const ENABLE_CONVERSATION_MODE = true

function ArenaPageContent() {
  const [prompt, setPrompt] = useState('')
  const [panelConfig, setPanelConfig] = useState(() => defaultPanelConfig())
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<DomainEvent[]>([])
  const [activePersona, setActivePersona] = useState<string | undefined>(undefined)
  const [speakerTime, setSpeakerTime] = useState<number>(0)
  const [members, setMembers] = useState<Member[]>(() => seatsToMembers(panelConfig.seats))
  const [eventsLoading, setEventsLoading] = useState(false)
  const [currentDebateId, setCurrentDebateId] = useState<string | null>(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const elapsedSecondsRef = useRef(0)
  useEffect(() => {
    elapsedSecondsRef.current = elapsedSeconds
  }, [elapsedSeconds])

  const [sessionStatus, setSessionStatus] = useState<ArenaRunUiState>('idle')
  const [latestScores, setLatestScores] = useState<ScoreItem[]>([])
  const [rateLimitNotice, setRateLimitNotice] = useState<{ detail: string; resetAt?: string } | null>(null)
  const [authStatus, setAuthStatus] = useState<'unknown' | 'authed' | 'guest'>('unknown')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [mode, setMode] = useState<'arena' | 'debate' | 'conversation'>('arena')
  const [gatewayPolicy, setGatewayPolicy] = useState<string>('auto')
  const [errorState, setErrorState] = useState<{ title?: string; message: string; hint?: string; retryable?: boolean } | null>(null)
  const [continueRunSheetOpen, setContinueRunSheetOpen] = useState(false)
  const [modelPanelOpen, setModelPanelOpen] = useState(false)
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>(() => panelConfig.seats.map((s) => s.model))
  const [activePrompt, setActivePrompt] = useState('')

  // Track workspace_opened on mount
  useEffect(() => {
    track('workspace_opened', { viewport_class: typeof window !== 'undefined' && window.innerWidth < 640 ? 'mobile' : 'desktop' })
  }, [])

  const promptSectionRef = useRef<HTMLDivElement | null>(null)

  const focusPromptPanel = useCallback(() => {
    promptSectionRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    })

    requestAnimationFrame(() => {
      const textarea = promptSectionRef.current?.querySelector("textarea")
      if (textarea instanceof HTMLTextAreaElement) {
        textarea.focus()
        textarea.select?.()
      }
    })

    track("live_hero_scroll_to_prompt_clicked")
  }, [])

  const searchParams = useSearchParams()
  const prefillPromptFrom = searchParams?.get('prefill_prompt_from')
  const prefillPromptText = searchParams?.get('prefill_prompt')
  const focusParam = searchParams?.get('focus')
  const source = searchParams?.get('source')

  useEffect(() => {
    if (prefillPromptFrom) {
      // Clear URL params so it doesn't trigger again on reload
      const url = new URL(window.location.href)
      url.searchParams.delete('prefill_prompt_from')
      url.searchParams.delete('source')
      window.history.replaceState({}, '', url.toString())

      getDebate(prefillPromptFrom)
        .then((data) => {
          if (data && data.prompt) {
            setPrompt(data.prompt)
            track('public_run_prompt_prefilled_to_arena', { ref_run: prefillPromptFrom, source })
          }
        })
        .catch((err) => {
          console.error("Failed to prefill prompt", err)
        })
    }
  }, [prefillPromptFrom, source])

  useEffect(() => {
    if (prefillPromptText) {
      setPrompt(decodeURIComponent(prefillPromptText))
      const url = new URL(window.location.href)
      url.searchParams.delete('prefill_prompt')
      window.history.replaceState({}, '', url.toString())
    }
  }, [prefillPromptText])

  useEffect(() => {
    if (focusParam === 'prompt') {
      const url = new URL(window.location.href)
      url.searchParams.delete('focus')
      window.history.replaceState({}, '', url.toString())
    }
  }, [focusParam])

  const { data: debatesData, isLoading: debatesLoading } = useDebatesList()
  const recentRuns = useMemo(() => {
    return (debatesData?.items || []).slice(0, 5)
  }, [debatesData])

  const { pushToast } = useToast()
  const { t } = useI18n()
  const router = useRouter()

  const runningRef = useRef(false)
  const currentDebateIdRef = useRef<string | null>(null)
  const manualStartAttemptedRef = useRef(false)
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const elapsedTimerRef = useRef<NodeJS.Timeout | null>(null)
  const stopStreamRef = useRef<((status?: ArenaRunUiState) => void) | null>(null)

  // Track F: SSE is owned exclusively by RunDetailClient/useRunWorkspace.
  // No local EventSource is created here.

  const reset = useCallback(() => {
    setEvents([])
    setActivePersona(undefined)
    setSpeakerTime(0)
    setEventsLoading(false)
    setLatestScores([])
    manualStartAttemptedRef.current = false
  }, [])

  const clearTimers = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (elapsedTimerRef.current) {
      clearInterval(elapsedTimerRef.current)
      elapsedTimerRef.current = null
    }
  }, [])

  const stopStream = useCallback((nextStatus: ArenaRunUiState = 'idle') => {
    clearTimers()
    setRunning(false)
    runningRef.current = false
    setEventsLoading(false)
    setSessionStatus(nextStatus)
    if (nextStatus === 'idle') {
      currentDebateIdRef.current = null
      setCurrentDebateId(null)
    }
    manualStartAttemptedRef.current = false
  }, [clearTimers])

  useEffect(() => {
    stopStreamRef.current = stopStream
  }, [stopStream])

  useEffect(() => {
    let cancelled = false
    getMe()
      .then((me) => {
        if (!cancelled) setAuthStatus(me ? 'authed' : 'guest')
      })
      .catch(() => {
        if (!cancelled) setAuthStatus('guest')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleModelSelectionSave = (ids: string[]) => {
    setSelectedModelIds(ids)
    // Convert to PanelSeatConfig
    const newSeats: PanelSeatConfig[] = ids.map((id) => {
      const match = AVAILABLE_MODELS.find((m) => m.id === id) || AVAILABLE_MODELS[0]
      return {
        seat_id: id,
        display_name: match.name,
        provider_key: match.providerKey,
        model: id,
        role_profile: 'architect',
      }
    })
    setPanelConfig((prev) => ({
      ...prev,
      seats: newSeats,
    }))
    setMembers(seatsToMembers(newSeats))
    track('model_config_saved', {
      seat_count: newSeats.length,
    })
  }

  const resumeParam = searchParams?.get('resume')
  useEffect(() => {
    if (resumeParam && authStatus === 'authed') {
      const intentKey = `pending_run_${resumeParam}`
      try {
        const stored = sessionStorage.getItem(intentKey)
        if (stored) {
          sessionStorage.removeItem(intentKey)
          const intent = JSON.parse(stored)
          if (intent.expiresAt > Date.now()) {
            setPrompt(intent.prompt)
            setMode(intent.mode)
            if (intent.models && intent.models.length > 0) {
              const newSeats = intent.models.map((id: string) => {
                const match = AVAILABLE_MODELS.find((m) => m.id === id) || AVAILABLE_MODELS[0]
                return {
                  seat_id: id,
                  display_name: match.name,
                  provider_key: match.providerKey,
                  model: id,
                  role_profile: 'architect',
                }
              })
              setPanelConfig({
                engine_version: 'parliament-v1',
                seats: newSeats,
              })
              setMembers(seatsToMembers(newSeats))
              setSelectedModelIds(intent.models)
            }
            
            // Auto-launch the resumed run
            const launchResume = async () => {
              reset()
              setRateLimitNotice(null)
              setErrorState(null)
              setSessionStatus('creating')
              setRunning(true)
              runningRef.current = true
              manualStartAttemptedRef.current = false
              try {
                const finalSeats = intent.models.map((id: string) => {
                  const match = AVAILABLE_MODELS.find((m) => m.id === id) || AVAILABLE_MODELS[0]
                  return {
                    seat_id: id,
                    display_name: match.name,
                    provider_key: match.providerKey,
                    model: id,
                    role_profile: 'architect',
                  }
                })
                const { id } = await startDebate({
                  prompt: intent.prompt,
                  panel_config: { engine_version: 'parliament-v1', seats: finalSeats },
                  mode: intent.mode,
                  gateway_policy: gatewayPolicy,
                })
                currentDebateIdRef.current = id
                setCurrentDebateId(id)
                setSessionStatus('created')
                track('debate_started', {
                  prompt_length: intent.prompt.length,
                  seat_count: finalSeats.length,
                  mode: intent.mode,
                })
                setSessionStatus('redirecting')
                router.replace(`/live?run=${id}`)
              } catch (error) {
                console.error('Failed to run resumed intent:', error)
                stopStream('terminal_error')
              }
            }
            launchResume()
          }
        }
      } catch (err) {
        console.error('Error resuming pending run:', err)
      }
      
      // Clean query parameter from URL
      const url = new URL(window.location.href)
      url.searchParams.delete('resume')
      window.history.replaceState({}, '', url.toString())
    }
  }, [resumeParam, authStatus, gatewayPolicy, router, stopStream, reset])

  const handlePanelChange = useCallback(
    (seats: PanelSeatConfig[]) => {
      setPanelConfig((prev) => ({ ...prev, seats }))
      setMembers(seatsToMembers(seats))
      track('model_config_saved', {
        seat_count: seats.length,
      })
    },
    [],
  )

  // Track F: Connection status is now derived from RunDetailClient/useRunWorkspace.
  // No local streamStatus tracking needed.

  const startElapsed = () => {
    if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current)
    setElapsedSeconds(0)
    elapsedTimerRef.current = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1)
    }, 1000)
  }

  const onStart = async () => {
    if (!prompt.trim()) return
    track('prompt_started', { prompt_length: prompt.length, mode })
    if (authStatus === 'guest') {
      setContinueRunSheetOpen(true)
      return
    }
    if (authStatus === 'unknown') {
      pushToast({
        title: t("live.signInRequired"),
        description: t("live.signInDescription"),
      })
      return
    }
    if (runningRef.current) {
      stopStream('idle')
    }
    reset()
    setRateLimitNotice(null)
    setErrorState(null)
    setSessionStatus('creating')
    setRunning(true)
    runningRef.current = true
    manualStartAttemptedRef.current = false
    try {
      const { id } = await startDebate({ prompt, panel_config: panelConfig, mode, gateway_policy: gatewayPolicy })
      currentDebateIdRef.current = id
      setCurrentDebateId(id)
      setSessionStatus('created')
      track('debate_started', {
        prompt_length: prompt.length,
        seat_count: panelConfig.seats.length,
        mode,
      })
      router.replace(`/live?run=${encodeURIComponent(id)}`, { scroll: false })
    } catch (error) {
      if (error instanceof ApiError) {
        const clientError = normalizeApiError(error, error.status)
        const info = getRateLimitInfo(error)
        if (info) {
          setRateLimitNotice(info)
          pushToast({ title: info.detail, variant: "error" })
        } else if (shouldRedirectToLogin(clientError)) {
          router.push('/login')
        } else {
          console.error(error)
          setErrorState({
            title: t("live.startError"),
            message: clientError.message || "An unexpected error occurred.",
            hint: clientError.hint,
            retryable: clientError.retryable
          });
        }
      } else {
        console.error(error)
        setErrorState({
          title: t("live.startError"),
          message: "An unexpected client-side error occurred.",
          retryable: true
        });
      }
      stopStream('terminal_error')
    }
  }

  useEffect(() => {
    return () => {
      stopStream()
    }
  }, [stopStream])

  const sessionStats = useMemo(() => {
    return {
      rounds: events.filter((event) => event.type === 'round_started').length,
      speeches: events.filter((event) => event.type === 'seat_message' || event.type === 'message').length,
      votes: events.filter((event) => event.type === 'score').length,
    }
  }, [events])

  const handlePresetSelected = (template: string) => {
    setPrompt((prev) => (prev ? `${prev.trim()}\n\n${template}` : template))
  }

  const handleCopyId = () => {
    if (!currentDebateId) return
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(currentDebateId).catch(() => null)
    }
  }

  const queryRunId = searchParams?.get('run')
  // Track C: URL is authoritative after creation/navigation
  const activeRunId = queryRunId || currentDebateId || null

  type ArenaPagePhase = 'idle' | 'creating' | 'active' | 'synthesizing' | 'completed' | 'failed' | 'cancelled'

  // Track B: RunSnapshot from RunDetailClient
  const [runSnapshot, setRunSnapshot] = useState<RunSnapshot | null>(null)

  const arenaPagePhase: ArenaPagePhase = (() => {
    if (sessionStatus === 'creating' || sessionStatus === 'redirecting') return 'creating'
    if (runSnapshot?.runPhase === 'completed') return 'completed'
    if (runSnapshot?.runPhase === 'failed') return 'failed'
    if (runSnapshot?.runPhase === 'cancelled') return 'cancelled'
    if (runSnapshot?.runPhase === 'synthesizing') return 'synthesizing'
    if (activeRunId && runSnapshot?.runPhase === 'active') return 'active'
    if (activeRunId) return 'active'
    return 'idle'
  })()

  const handleRunSnapshot = useCallback((snapshot: RunSnapshot) => {
    setRunSnapshot(snapshot)
    if (snapshot.isTerminal) {
      setRunning(false)
      runningRef.current = false
    }
  }, [])

  const resetToNewRun = useCallback(() => {
    reset()
    setCurrentDebateId(null)
    currentDebateIdRef.current = null
    setSessionStatus('idle')
    setRunSnapshot(null)
    setErrorState(null)
    router.replace('/live', { scroll: false })
  }, [router, reset])

  return (
    <main id="main" className="relative min-h-[calc(100vh-8rem)] flex flex-col items-center space-y-6 p-4 lg:p-6">
      {rateLimitNotice ? (
        <RateLimitBanner
          detail={rateLimitNotice.detail}
          resetAt={rateLimitNotice.resetAt}
          actions={
            <button
              className="rounded-full border border-rose-200 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-rose-700 transition hover:bg-white"
              onClick={() => setRateLimitNotice(null)}
            >
              Dismiss
            </button>
          }
        />
      ) : null}
      {authStatus === 'guest' ? (
        <div className="rounded-2xl border border-amber-100/80 bg-white/80 p-5 text-stone-900 shadow-sm backdrop-blur dark:border-amber-900/40 dark:bg-stone-900/70 dark:text-amber-50">
          <p className="text-sm font-semibold text-amber-900 dark:text-amber-100">{t("live.signInRequired")}</p>
          <p className="mt-1 text-sm text-stone-700 dark:text-amber-50/80">{t("live.signInDescription")}</p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button variant="amber" onClick={() => router.push("/login?next=/live")}>
              {t("live.signInCta")}
            </Button>
            <Link href="/register" className="text-sm font-semibold text-amber-800 underline-offset-4 hover:underline focus-ring dark:text-amber-100">
              {t("auth.register.footerLink")}
            </Link>
          </div>
        </div>
      ) : null}

      {/* Idle-only ParliamentHome on wide displays */}
      {sessionStatus === 'idle' && !activeRunId && (
        <div className="hidden xl:block w-full max-w-[950px] mx-auto px-4 lg:px-6">
          <ParliamentHome
            members={members}
            activeMemberId={members.find((member) => member.name === activePersona)?.id}
            speakerSeconds={speakerTime}
            stats={sessionStats}
            voteResults={latestScores}
            onStart={focusPromptPanel}
            running={running}
          />
        </div>
      )}

      {/* Composer shell — always max-w-4xl */}
      <div className="w-full max-w-4xl mx-auto px-4 lg:px-6 space-y-6">
        {errorState && (
          <ErrorBanner
            title={errorState.title}
            message={errorState.message}
            variant="error"
            retryAction={errorState.retryable ? onStart : undefined}
            onDismiss={() => setErrorState(null)}
          />
        )}

        {/* Inline retry after creation failure — preserve prompt */}
        {arenaPagePhase === 'idle' && errorState?.retryable && prompt.trim() && (
          <div className="text-xs text-muted-foreground text-center">
            You can edit your prompt and try again
          </div>
        )}

        {!running && sessionStatus === 'idle' && (
          <FirstRunGuide onPrefill={(text) => { setPrompt(text); focusPromptPanel(); }} />
        )}

        <IdleDecisionComposer
          value={prompt}
          onChange={setPrompt}
          onSubmit={onStart}
          mode={mode === 'debate' ? 'debate' : 'arena'}
          onModeChange={(newMode) => {
            setMode(newMode)
            track('mode_selected', { mode: newMode })
          }}
          isLoading={running}
          disabled={running}
          onConfigureModels={() => setModelPanelOpen(true)}
          runPhase={arenaPagePhase === 'idle' ? 'idle' : arenaPagePhase === 'creating' ? 'creating' : arenaPagePhase === 'completed' ? 'completed' : arenaPagePhase === 'failed' ? 'failed' : arenaPagePhase === 'cancelled' ? 'cancelled' : arenaPagePhase === 'synthesizing' ? 'synthesizing' : 'active'}
          onNewRun={resetToNewRun}
        />

        {!activeRunId && <PromptPresets onPresetSelected={handlePresetSelected} />}

        {authStatus === 'authed' && !activeRunId && (
          <div className="mt-8 border-t border-slate-100 pt-8 dark:border-slate-800">
            <DashboardRunsHistory
              debates={recentRuns}
              debatesLoading={debatesLoading}
              onNewRun={() => {
                const textareas = document.getElementsByTagName('textarea');
                if (textareas.length > 0) {
                  textareas[0].focus();
                  textareas[0].scrollIntoView({ behavior: 'smooth' });
                }
              }}
            />
          </div>
        )}
      </div>

      {/* Active workspace — wider container */}
      {activeRunId && (
        <div className="w-full max-w-[1600px] 2xl:max-w-[1800px] mx-auto px-4 lg:px-6 mt-2 sm:mt-8">
          <RunDetailClient
            key={activeRunId}
            runId={activeRunId}
            surface="live"
            recentRuns={recentRuns}
            recentRunsLoading={debatesLoading}
            onNewRun={resetToNewRun}
            onRunSnapshot={handleRunSnapshot}
          />
        </div>
      )}

      {/* Track L: LivePanel removed — events are handled by RunDetailClient */}

      {/* Advanced settings drawer */}
      <AdvancedSettingsDrawer
        open={advancedOpen}
        onOpenChange={setAdvancedOpen}
        panelConfig={panelConfig.seats}
        onPanelConfigChange={handlePanelChange}
        gatewayPolicy={gatewayPolicy}
        onGatewayPolicyChange={setGatewayPolicy}
      />
      <ContinueRunSheet
        open={continueRunSheetOpen}
        onOpenChange={setContinueRunSheetOpen}
        promptText={activePrompt || prompt}
        selectedModels={selectedModelIds}
        mode={mode === 'debate' ? 'debate' : 'arena'}
      />
      <ModelPanelSheet
        open={modelPanelOpen}
        onOpenChange={setModelPanelOpen}
        selectedModelIds={selectedModelIds}
        onSave={handleModelSelectionSave}
      />
    </main>
  )
}

export default function Page() {
  return (
    <Suspense fallback={<div className="p-6 text-center text-slate-500">Loading Arena...</div>}>
      <ArenaPageContent />
    </Suspense>
  )
}
