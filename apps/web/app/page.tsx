'use client'

import { useEffect, useRef, useState } from 'react'
import Hero from '@/components/parliament/Hero'
import ParliamentChamber from '@/components/parliament/ParliamentChamber'
import LivePanel from '@/components/consultaion/consultaion/live-panel'
import { startDebate, streamDebate, getMembers } from '@/lib/api'
import type { Member } from '@/components/parliament/types'

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
  const [membersLoading, setMembersLoading] = useState(true)
  const [eventsLoading, setEventsLoading] = useState(false)

  const esRef = useRef<EventSource | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptRef = useRef(0)
  const currentDebateIdRef = useRef<string | null>(null)
  const runningRef = useRef(false)

  const reset = () => {
    setEvents([])
    setActivePersona(undefined)
    setSpeakerTime(0)
    setVote(undefined)
    setEventsLoading(false)
  }

  const clearTimers = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }

  const stopStream = () => {
    esRef.current?.close()
    esRef.current = null
    clearTimers()
    reconnectAttemptRef.current = 0
    currentDebateIdRef.current = null
    setRunning(false)
    runningRef.current = false
    setEventsLoading(false)
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
        }
        if (msg.type === 'final') {
          if (msg.meta?.ranking) {
            setVote({
              method: msg.meta?.vote?.method ?? 'borda',
              ranking: msg.meta.ranking,
            })
          }
          stopStream()
        }
      } catch (error) {
        console.error('Failed to parse event', error)
      }
    }
    es.onerror = () => {
      es.close()
      if (runningRef.current) {
        scheduleReconnect()
      }
    }
  }

  const onStart = async () => {
    if (!prompt.trim()) return
    reset()
    setRunning(true)
    runningRef.current = true
    try {
      const { id } = await startDebate({ prompt })
      currentDebateIdRef.current = id
      reconnectAttemptRef.current = 0
      openStream(id)
      timerRef.current = setInterval(() => setSpeakerTime((t) => t + 1), 1000)
    } catch (error) {
      console.error(error)
      stopStream()
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
      .finally(() => {
        if (active) {
          setMembersLoading(false)
        }
      })
    return () => {
      active = false
      stopStream()
    }
  }, [])

  return (
    <main id="main" className="space-y-6 p-4">
      <Hero onStart={onStart} />
      {membersLoading ? (
        <section className="py-12">
          <div className="container mx-auto px-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 3 }).map((_, idx) => (
                <div key={idx} className="h-32 animate-pulse rounded-xl bg-muted/40" />
              ))}
            </div>
          </div>
        </section>
      ) : (
        <ParliamentChamber members={members} activeId={activePersona} speakerSeconds={speakerTime} />
      )}
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
