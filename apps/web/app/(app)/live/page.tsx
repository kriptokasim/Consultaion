'use client'

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import LivePanel from "@/components/consultaion/consultaion/live-panel";
import ParliamentHome from "@/components/parliament/ParliamentHome";
import SessionHUD from "@/components/parliament/SessionHUD";
import RateLimitBanner from "@/components/parliament/RateLimitBanner";
import type { Member, ScoreItem } from "@/components/parliament/types";
import { ErrorBanner } from "@/components/ui/error-banner";
import { ApiError, getRateLimitInfo, startDebate, startDebateRun } from "@/lib/api";
import { useEventSource } from "@/lib/sse";
import { defaultPanelConfig, type PanelSeatConfig } from "@/lib/panels";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { getMe } from "@/lib/auth";
import { useI18n } from "@/lib/i18n/client";
import { DebateReplay } from "@/components/debate/DebateReplay";
import { PromptPanel, PromptPresets, AdvancedSettingsDrawer, DebateProgressBar } from "@/components/prompt";
import { track } from "@/lib/analytics";
import { OnboardingHint } from "@/components/ui/onboarding-hint";

const FALLBACK_MEMBERS: Member[] = [
  { id: 'Analyst', name: 'Analyst', role: 'agent' },
  { id: 'Critic', name: 'Critic', role: 'critic' },
  { id: 'Builder', name: 'Builder', role: 'agent' },
  { id: 'JudgeAlpha', name: 'JudgeAlpha', role: 'judge' },
]

const seatsToMembers = (seats: PanelSeatConfig[]): Member[] =>
  seats.map((seat) => ({
    id: seat.seat_id,
    name: seat.display_name,
    role: seat.role_profile === 'judge' ? 'judge' : seat.role_profile === 'risk_officer' ? 'critic' : 'agent',
    party: seat.provider_key,
  }))

type VoteMeta = {
  method?: string
  ranking?: string[]
}

const ENABLE_CONVERSATION_MODE = process.env.NEXT_PUBLIC_ENABLE_CONVERSATION_MODE === 'true' || process.env.NEXT_PUBLIC_ENABLE_CONVERSATION_MODE === '1'

export default function Page() {
  const [prompt, setPrompt] = useState('Draft a national EV policy')
  const [panelConfig, setPanelConfig] = useState(() => defaultPanelConfig())
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<any[]>([])
  const [activePersona, setActivePersona] = useState<string | undefined>(undefined)
  const [speakerTime, setSpeakerTime] = useState<number>(0)
  const [vote, setVote] = useState<VoteMeta | undefined>(undefined)
  const [members, setMembers] = useState<Member[]>(() => seatsToMembers(panelConfig.seats))
  const [eventsLoading, setEventsLoading] = useState(false)
  const [currentDebateId, setCurrentDebateId] = useState<string | null>(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [sessionStatus, setSessionStatus] = useState<'idle' | 'running' | 'completed' | 'error'>('idle')
  const [latestScores, setLatestScores] = useState<ScoreItem[]>([])
  const [rateLimitNotice, setRateLimitNotice] = useState<{ detail: string; resetAt?: string } | null>(null)
  const [authStatus, setAuthStatus] = useState<'unknown' | 'authed' | 'guest'>('unknown')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [mode, setMode] = useState<'debate' | 'conversation'>('debate')
  const [truncated, setTruncated] = useState(false)
  const [truncateReason, setTruncateReason] = useState<string | null>(null)
  const [errorState, setErrorState] = useState<{ title?: string; message: string; hint?: string; retryable?: boolean } | null>(null)

  const { pushToast } = useToast()
  const { t } = useI18n()
  const router = useRouter()

  const runningRef = useRef(false)
  const currentDebateIdRef = useRef<string | null>(null)
  const manualStartAttemptedRef = useRef(false)
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const elapsedTimerRef = useRef<NodeJS.Timeout | null>(null)
  const stopStreamRef = useRef<((status?: 'idle' | 'completed' | 'error') => void) | null>(null)

  const manualStartMode = !ENABLE_CONVERSATION_MODE
  const shouldStream = running && !!currentDebateId
  const streamUrl = currentDebateId ? `/debates/${currentDebateId}/stream` : null

  const handleStreamEvent = useCallback(
    (msg: any) => {
      if (msg.type === 'error') {
        console.error('Stream error:', msg)
        stopStreamRef.current?.('error')
        return
      }
      setEvents((prev) => [...prev, msg])

      if (msg.type === 'seat_message' || msg.type === 'message') {
        setActivePersona(msg.seat_name || msg.actor)
        setSpeakerTime(0)
      } else if (msg.type === 'round_started') {
        setActivePersona(undefined)
        setSpeakerTime(0)
      } else if (msg.type === 'score') {
        setLatestScores((prev) => {
          const newScores = [...prev, { persona: msg.persona, score: msg.score }]
          return newScores.slice(-5) // Keep last 5
        })
      }

      if (msg.type === 'final') {
        if (msg.meta?.ranking) {
          setVote({
            method: msg.meta?.vote?.method ?? 'borda',
            ranking: msg.meta.ranking,
          })
        }
        if (msg.meta?.truncated) {
          setTruncated(true)
          setTruncateReason(msg.meta.truncate_reason)
        }
        track('debate_completed', {
          debate_id: currentDebateId,
          duration_ms: elapsedSeconds * 1000,
        })
        stopStreamRef.current?.('completed')
      }
    },
    [setEvents, setActivePersona, setVote, setLatestScores],
  )

  const handleStreamError = useCallback(() => {
    if (!runningRef.current || !currentDebateIdRef.current) {
      return
    }
    if (manualStartMode && !manualStartAttemptedRef.current) {
      manualStartAttemptedRef.current = true
      startDebateRun(currentDebateIdRef.current)
        .then(() => {
          setSessionStatus('running')
        })
        .catch((error) => {
          console.error('Manual start failed', error)
          setSessionStatus('error')
        })
      return
    }
    setSessionStatus('error')
  }, [manualStartMode])

  const { status: streamStatus, close: closeStream } = useEventSource<any>(shouldStream ? streamUrl : null, {
    enabled: shouldStream,
    withCredentials: true,
    onEvent: handleStreamEvent,
    onError: handleStreamError,
  })

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

  const stopStream = useCallback((nextStatus: 'idle' | 'completed' | 'error' = 'idle') => {
    closeStream()
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
  }, [clearTimers, closeStream])

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

  useEffect(() => {
    if (streamStatus === 'connecting' || streamStatus === 'reconnecting') {
      setEventsLoading(true)
    } else if (streamStatus === 'connected') {
      setEventsLoading(false)
    }
  }, [streamStatus])

  const startElapsed = () => {
    if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current)
    setElapsedSeconds(0)
    elapsedTimerRef.current = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1)
    }, 1000)
  }

  const onStart = async () => {
    if (!prompt.trim()) return
    if (authStatus === 'guest') {
      pushToast({
        title: t("live.signInRequired"),
        description: t("live.signInDescription"),
        variant: "error",
      })
      router.push("/login?next=/live")
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
    setRunning(true)
    runningRef.current = true
    manualStartAttemptedRef.current = false
    try {
      const { id } = await startDebate({ prompt, panel_config: panelConfig, mode })
      currentDebateIdRef.current = id
      setCurrentDebateId(id)
      setSessionStatus('running')
      timerRef.current = setInterval(() => setSpeakerTime((t) => t + 1), 1000)
      startElapsed()
      track('debate_started', {
        prompt_length: prompt.length,
        seat_count: panelConfig.seats.length,
        mode,
      })
    } catch (error) {
      if (error instanceof ApiError) {
        const info = getRateLimitInfo(error)
        if (info) {
          setRateLimitNotice(info)
          pushToast({ title: info.detail, variant: "error" })
        } else {
          console.error(error)
          const body = error.body as any;
          const errData = body?.error || {};
          setErrorState({
            title: t("live.startError"),
            message: errData.message || error.message || "An unexpected error occurred.",
            hint: errData.hint,
            retryable: errData.retryable
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
      stopStream('error')
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

  return (
    <main id="main" className="space-y-6 p-4 lg:p-6">
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
      <ParliamentHome
        members={members}
        activeMemberId={members.find((member) => member.name === activePersona)?.id}
        speakerSeconds={speakerTime}
        stats={sessionStats}
        voteResults={latestScores}
        onStart={onStart}
        running={running}
      />
      <SessionHUD
        status={sessionStatus}
        debateId={currentDebateId}
        elapsedSeconds={elapsedSeconds}
        activePersona={activePersona}
        onCopy={handleCopyId}
      />

      {/* New centered prompt workspace */}
      <div className="space-y-4">
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

        <OnboardingHint id="live_chamber" text={t("onboarding.live.chamberHint")} className="mb-4" />

        <PromptPanel
          value={prompt}
          onChange={setPrompt}
          onSubmit={onStart}
          status={running ? 'running' : sessionStatus === 'error' ? 'error' : 'idle'}
          disabled={running || authStatus === 'guest'}
          isSubmitLoading={running}
          submitLabel={t("live.start")}
          onAdvancedSettingsClick={() => {
            setAdvancedOpen(true)
            track('settings_opened', { source: 'prompt_panel' })
          }}
          mode={mode}
          onModeChange={ENABLE_CONVERSATION_MODE ? setMode : undefined}
        />

        <OnboardingHint id="live_prompt" text={t("onboarding.live.promptHint")} className="mt-2" />

        <PromptPresets onPresetSelected={handlePresetSelected} />
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
      />
      {currentDebateId ? (
        <section className="rounded-3xl border border-amber-200/70 bg-white/90 p-6 shadow-[0_18px_40px_rgba(112,73,28,0.12)] dark:border-amber-900/50 dark:bg-stone-900/70">
          <DebateReplay debateId={currentDebateId} />
        </section>
      ) : null}
    </main>
  )
}
