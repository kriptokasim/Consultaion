'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import LivePanel from "@/components/consultaion/consultaion/live-panel";
import ParliamentHome from "@/components/parliament/ParliamentHome";
import SessionHUD from "@/components/parliament/SessionHUD";
import RateLimitBanner from "@/components/parliament/RateLimitBanner";
import PromptSuggestions from "@/components/parliament/PromptSuggestions";
import PanelConfigurator from "@/components/parliament/PanelConfigurator";
import type { Member, ScoreItem } from "@/components/parliament/types";
import { ApiError, getRateLimitInfo, startDebate, startDebateRun } from "@/lib/api";
import { useEventSource } from "@/lib/sse";
import { defaultPanelConfig, type PanelSeatConfig } from "@/lib/panels";

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

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const elapsedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const currentDebateIdRef = useRef<string | null>(null)
  const runningRef = useRef(false)
  const manualStartAttemptedRef = useRef(false)
  const stopStreamRef = useRef<((nextStatus: 'idle' | 'completed' | 'error') => void) | null>(null)
  const manualStartMode = (process.env.NEXT_PUBLIC_AUTORUN_HINT ?? "on") === "off"
  const apiBase = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "")

  const streamUrl = useMemo(() => {
    if (!currentDebateId) return null
    const path = `/debates/${currentDebateId}/stream`
    return apiBase ? `${apiBase}${path}` : path
  }, [apiBase, currentDebateId])

  const shouldStream = Boolean(streamUrl) && running

  const handleStreamEvent = useCallback(
    (msg: any) => {
      setEvents((prev) => [...prev, msg])
      setEventsLoading(false)
      if (msg.type === 'seat_message') {
        if (msg.seat_name || msg.seat_id) {
          setActivePersona(msg.seat_name ?? msg.seat_id)
        }
      } else if (msg.type === 'message') {
        const persona = msg.revised?.[0]?.persona ?? msg.candidates?.[0]?.persona
        if (persona) setActivePersona(persona)
      }
      if (msg.type === 'score' && Array.isArray(msg.scores)) {
        const ranking = [...msg.scores].sort((a: any, b: any) => b.score - a.score).map((s: any) => s.persona)
        setVote({ method: 'borda', ranking })
        setLatestScores(
          msg.scores.map((score: any) => ({
            persona: score.persona,
            score: Number(score.score) || 0,
            rationale: score.rationale,
          })),
        )
      }
      if (msg.type === 'final') {
        if (msg.meta?.ranking) {
          setVote({
            method: msg.meta?.vote?.method ?? 'borda',
            ranking: msg.meta.ranking,
          })
        }
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

  const handlePanelChange = useCallback(
    (seats: PanelSeatConfig[]) => {
      setPanelConfig((prev) => ({ ...prev, seats }))
      setMembers(seatsToMembers(seats))
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
    if (runningRef.current) {
      stopStream('idle')
    }
    reset()
    setRateLimitNotice(null)
    setRunning(true)
    runningRef.current = true
    manualStartAttemptedRef.current = false
    try {
      const { id } = await startDebate({ prompt, panel_config: panelConfig })
      currentDebateIdRef.current = id
      setCurrentDebateId(id)
      setSessionStatus('running')
      timerRef.current = setInterval(() => setSpeakerTime((t) => t + 1), 1000)
      startElapsed()
    } catch (error) {
      if (error instanceof ApiError) {
        const info = getRateLimitInfo(error)
        if (info) {
          setRateLimitNotice(info)
        } else {
          console.error(error)
        }
      } else {
        console.error(error)
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
      <div className="grid gap-4 lg:grid-cols-[1.4fr_0.6fr]">
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
        />
        <div className="space-y-4">
          <PanelConfigurator seats={panelConfig.seats} onChange={handlePanelChange} />
          <PromptSuggestions onSelect={setPrompt} />
        </div>
      </div>
    </main>
  )
}
