'use client'

import { useEffect, useMemo, useRef, useState } from "react";
import LivePanel from "@/components/consultaion/consultaion/live-panel";
import ParliamentHome from "@/components/parliament/ParliamentHome";
import SessionHUD from "@/components/parliament/SessionHUD";
import type { Member, ScoreItem } from "@/components/parliament/types";
import { ApiError, getMembers, startDebate, streamDebate } from "@/lib/api";

const FALLBACK_MEMBERS: Member[] = [
  { id: 'Analyst', name: 'Analyst', role: 'agent' },
  { id: 'Critic', name: 'Critic', role: 'critic' },
  { id: 'Builder', name: 'Builder', role: 'agent' },
  { id: 'JudgeAlpha', name: 'JudgeAlpha', role: 'judge' },
]

type VoteMeta = {
  method?: string
  ranking?: string[]
}

const RECONNECT_STEPS = [1000, 2000, 5000, 10000]

export default function Page() {
  const [prompt, setPrompt] = useState('Draft a national EV policy')
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<any[]>([])
  const [activePersona, setActivePersona] = useState<string | undefined>(undefined)
  const [speakerTime, setSpeakerTime] = useState<number>(0)
  const [vote, setVote] = useState<VoteMeta | undefined>(undefined)
  const [members, setMembers] = useState<Member[]>(FALLBACK_MEMBERS)
  const [eventsLoading, setEventsLoading] = useState(false)
  const [currentDebateId, setCurrentDebateId] = useState<string | null>(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [sessionStatus, setSessionStatus] = useState<'idle' | 'running' | 'completed' | 'error'>('idle')
  const [latestScores, setLatestScores] = useState<ScoreItem[]>([])
  const [rateLimitNotice, setRateLimitNotice] = useState<{ detail: string; resetAt?: string } | null>(null)

  const esRef = useRef<EventSource | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptRef = useRef(0)
  const currentDebateIdRef = useRef<string | null>(null)
  const runningRef = useRef(false)
  const elapsedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const reset = () => {
    setEvents([])
    setActivePersona(undefined)
    setSpeakerTime(0)
    setVote(undefined)
    setEventsLoading(false)
    setLatestScores([])
  }

  const clearTimers = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (elapsedTimerRef.current) {
      clearInterval(elapsedTimerRef.current)
      elapsedTimerRef.current = null
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }

  const stopStream = (nextStatus: 'idle' | 'completed' | 'error' = 'idle') => {
    esRef.current?.close()
    esRef.current = null
    clearTimers()
    reconnectAttemptRef.current = 0
    currentDebateIdRef.current = null
    setRunning(false)
    runningRef.current = false
    setEventsLoading(false)
    setSessionStatus(nextStatus)
    if (nextStatus === 'idle') {
      setCurrentDebateId(null)
    }
  }

  const startElapsed = () => {
    if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current)
    setElapsedSeconds(0)
    elapsedTimerRef.current = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1)
    }, 1000)
  }

  const scheduleReconnect = () => {
    if (!runningRef.current || !currentDebateIdRef.current) {
      return
    }
    const attempt = reconnectAttemptRef.current
    const delay = RECONNECT_STEPS[Math.min(attempt, RECONNECT_STEPS.length - 1)]
    reconnectAttemptRef.current = attempt + 1
    setEventsLoading(true)
    reconnectTimerRef.current = setTimeout(() => {
      if (!currentDebateIdRef.current) return
      openStream(currentDebateIdRef.current)
    }, delay)
  }

  const openStream = (debateId: string) => {
    esRef.current?.close()
    const es = streamDebate(debateId)
    esRef.current = es
    setEventsLoading(true)
    es.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        setEvents((prev) => [...prev, msg])
        setEventsLoading(false)
        if (msg.type === 'message') {
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
          stopStream('completed')
        }
      } catch (error) {
        console.error('Failed to parse event', error)
      }
    }
    es.onerror = () => {
      es.close()
      setSessionStatus('error')
      if (runningRef.current) {
        scheduleReconnect()
      }
    }
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
    try {
      const { id } = await startDebate({ prompt })
      currentDebateIdRef.current = id
      setCurrentDebateId(id)
      reconnectAttemptRef.current = 0
      setSessionStatus('running')
      openStream(id)
      timerRef.current = setInterval(() => setSpeakerTime((t) => t + 1), 1000)
      startElapsed()
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) {
        const detail =
          (typeof error.body === 'object' && error.body?.detail) || 'Rate limit exceeded. Please wait before summoning another session.'
        const resetAt =
          typeof error.body === 'object' && typeof error.body?.reset_at === 'string' ? error.body.reset_at : undefined
        setRateLimitNotice({ detail, resetAt })
      } else {
        console.error(error)
      }
      stopStream('error')
    }
  }

  useEffect(() => {
    let active = true
    getMembers()
      .then((payload) => {
        if (!active) return
        const fetched = Array.isArray(payload?.members) ? payload.members : []
        if (fetched.length) {
          setMembers(
            fetched.map((member: any) => ({
              id: member.id ?? member.name,
              name: member.name ?? member.id,
              role: member.role ?? 'agent',
              party: member.party,
            })),
          )
        } else {
          setMembers(FALLBACK_MEMBERS)
        }
      })
      .catch(() => {
        if (active) {
          setMembers(FALLBACK_MEMBERS)
        }
      })
    return () => {
      active = false
      stopStream()
    }
  }, [])

  const sessionStats = useMemo(() => {
    return {
      rounds: events.filter((event) => event.type === 'round_started').length,
      speeches: events.filter((event) => event.type === 'message').length,
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
    <main id="main" className="space-y-6 p-4">
      {rateLimitNotice ? (
        <div
          role="alert"
          aria-live="polite"
          className="flex items-start justify-between gap-4 rounded-3xl border border-rose-200 bg-rose-50/80 p-4 text-sm text-rose-900 shadow-sm"
        >
          <div>
            <p className="font-semibold">Rate limit reached</p>
            <p className="mt-1 text-rose-800">{rateLimitNotice.detail}</p>
            {rateLimitNotice.resetAt ? (
              <p className="mt-1 text-xs uppercase tracking-wide text-rose-700">
                Resets around {new Date(rateLimitNotice.resetAt).toLocaleTimeString()}
              </p>
            ) : null}
          </div>
          <button
            className="rounded-full border border-rose-200 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-rose-700 transition hover:bg-white"
            onClick={() => setRateLimitNotice(null)}
          >
            Dismiss
          </button>
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
    </main>
  )
}
