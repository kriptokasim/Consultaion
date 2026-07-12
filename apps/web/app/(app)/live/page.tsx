'use client'

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import LivePanel from "@/components/consultaion/consultaion/live-panel";
import ParliamentHome from "@/components/parliament/ParliamentHome";
import SessionHUD from "@/components/parliament/SessionHUD";
import RateLimitBanner from "@/components/parliament/RateLimitBanner";
import type { Member, ScoreItem } from "@/components/parliament/types";
import type { ArenaRunUiState } from "@/components/parliament/StatusPill";
import { ErrorBanner } from "@/components/ui/error-banner";
import { ApiError, getRateLimitInfo, startDebate, getDebate } from "@/lib/api";
import { API_ORIGIN } from "@/lib/config/runtime";
import { defaultPanelConfig, type PanelSeatConfig } from "@/lib/panels";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { getMe } from "@/lib/auth";
import { useI18n } from "@/lib/i18n/client";
import { DebateReplay } from "@/components/debate/DebateReplay";
import { PromptPanel, PromptPresets, AdvancedSettingsDrawer, DebateProgressBar, IdleDecisionComposer, ActiveWorkspaceComposer } from "@/components/prompt";
import { ModelPanelSheet, AVAILABLE_MODELS } from "@/components/arena/ModelPanelSheet";
import { ContinueRunSheet } from "@/components/auth/ContinueRunSheet";
import { track } from "@/lib/analytics";
import { OnboardingHint } from "@/components/ui/onboarding-hint";
import { useDebatesList } from "@/lib/api/hooks/useDebatesList";
import { DashboardRunsHistory } from "@/components/dashboard/DashboardRunsHistory";
import { type DomainEvent } from "@/lib/api/eventContract";
import { normalizeApiError, type ClientError, shouldRedirectToLogin, getCorrelationId } from "@/lib/api/errorContract";
import { ConnectionIndicator, type ConnectionStatus } from "@/components/connection/ConnectionIndicator";
import { FirstRunGuide } from "@/components/onboarding/FirstRunGuide";

import RunDetailClient from "../runs/[id]/RunDetailClient";

const seatsToMembers = (seats: PanelSeatConfig[]): Member[] =>
  seats.map((seat) => ({
    id: seat.seat_id,
    name: seat.display_name,
    role: seat.role_profile === 'judge' ? 'judge' : seat.role_profile === 'risk_officer' ? 'critic' : 'agent',
    party: seat.provider_key,
  }))

const FALLBACK_MEMBERS: Member[] = seatsToMembers(defaultPanelConfig().seats)

type VoteMeta = {
  method?: string
  ranking?: string[]
}

const ENABLE_CONVERSATION_MODE = true

function ArenaPageContent() {
  const [prompt, setPrompt] = useState('')
  const [panelConfig, setPanelConfig] = useState(() => defaultPanelConfig())
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<DomainEvent[]>([])
  const [activePersona, setActivePersona] = useState<string | undefined>(undefined)
  const [speakerTime, setSpeakerTime] = useState<number>(0)
  const [vote, setVote] = useState<VoteMeta | undefined>(undefined)
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
  const [autoFocus, setAutoFocus] = useState(false)
  const [truncated, setTruncated] = useState(false)
  const [truncateReason, setTruncateReason] = useState<string | null>(null)
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
      setAutoFocus(true)
      const url = new URL(window.location.href)
      url.searchParams.delete('prefill_prompt')
      window.history.replaceState({}, '', url.toString())
    }
  }, [prefillPromptText])

  useEffect(() => {
    if (focusParam === 'prompt') {
      setAutoFocus(true)
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

  const reset = () => {
    setEvents([])
    setActivePersona(undefined)
    setSpeakerTime(0)
    setVote(undefined)
    setEventsLoading(false)
    setLatestScores([])
    manualStartAttemptedRef.current = false
  }

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
  }, [resumeParam, authStatus, gatewayPolicy, router, stopStream])

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
  const activeRunId = currentDebateId || queryRunId || null

  type ArenaPagePhase = 'idle' | 'creating' | 'active' | 'terminal'

  const arenaPagePhase: ArenaPagePhase = (() => {
    if (sessionStatus === 'creating' || sessionStatus === 'redirecting') return 'creating'
    if (activeRunId) return 'active'
    return 'idle'
  })()

  const resetToNewRun = useCallback(() => {
    reset()
    setCurrentDebateId(null)
    currentDebateIdRef.current = null
    setSessionStatus('idle')
    setErrorState(null)
    router.replace('/live', { scroll: false })
  }, [router, reset])

  return (
    <main id="main" className="relative min-h-[calc(100vh-8rem)] flex flex-col items-center justify-center space-y-6 p-4 lg:p-6">
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
      <div className={`w-full max-w-[1800px] mx-auto flex flex-col ${sessionStatus === 'idle' ? 'xl:flex-row' : ''} gap-8 xl:gap-12 2xl:gap-24 items-start justify-center transition-all duration-500`}>
        {/* Background / Info Banner on the left — only when idle and no active run */}
        <div className={sessionStatus === 'idle' && !activeRunId ? "hidden xl:block xl:flex-[1.3] xl:max-w-[950px] transition-all duration-1000 origin-left opacity-100" : "hidden"}>
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

        {/* Main composer and workspace (center-left) */}
        <div className={`z-10 w-full mx-auto ${sessionStatus === 'idle' ? 'xl:flex-[1.1] max-w-4xl xl:max-w-[850px] xl:mx-0' : 'max-w-4xl'} flex flex-col space-y-6 transition-all duration-500`}>
        {sessionStatus !== 'idle' && (
          <SessionHUD
            status={sessionStatus}
            debateId={currentDebateId}
            elapsedSeconds={elapsedSeconds}
            activePersona={activePersona}
            onCopy={handleCopyId}
            runUrl={currentDebateId ? `/runs/${currentDebateId}` : null}
          />
        )}
        {sessionStatus !== 'idle' && (
          <ConnectionIndicator
            status={running && activeRunId ? 'reconnecting' :
                   running ? 'degraded' : 'idle'}
            className="ml-2"
          />
        )}

        {/* New centered prompt workspace */}
        <div ref={promptSectionRef} className="space-y-4 scroll-mt-28 w-full mt-8 md:mt-16">
          <DebateProgressBar active={running} />

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
          <FirstRunGuide onPrefill={(text) => { setPrompt(text); setAutoFocus(true); focusPromptPanel(); }} />
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
          runPhase={arenaPagePhase === 'idle' ? 'idle' : arenaPagePhase === 'creating' ? 'creating' : activeRunId ? 'active' : 'idle'}
          onNewRun={resetToNewRun}
        />

        {/* Arena Run Content — rendered below the centered composer when a run is active */}
        {activeRunId && (
          <div className="mt-8">
            <RunDetailClient
              runId={activeRunId}
              surface="live"
              recentRuns={recentRuns}
              recentRunsLoading={debatesLoading}
              onNewRun={resetToNewRun}
            />
          </div>
        )}

        <PromptPresets onPresetSelected={handlePresetSelected} />

        {authStatus === 'authed' && (
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
      </div>
      </div>

      {/* Keep existing LivePanel for events display */}
      {events.length > 0 && (
        <div className="mt-6">
          <LivePanel
            prompt={prompt}
            onPromptChange={setPrompt}
            onStart={onStart}
            onStop={stopStream}
            running={running}
            events={events}
            activePersona={activePersona}
            speakerTime={speakerTime}
            vote={vote}
            loading={eventsLoading}
            mode={mode}
            truncated={truncated}
            truncateReason={truncateReason}
          />
        </div>
      )}

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
      {currentDebateId && events.length > 0 && (
        <section className="rounded-3xl border border-amber-200/70 bg-white/90 p-6 shadow-[0_18px_40px_#70491c1f] dark:border-amber-900/50 dark:bg-stone-900/70">
          <DebateReplay debateId={currentDebateId} />
        </section>
      )}
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
