'use client'

import { useEffect, useRef, useState } from 'react'
import Hero from '@/components/parliament/Hero'
import ParliamentChamber from '@/components/parliament/ParliamentChamber'
import LivePanel from '@/components/consultaion/consultaion/live-panel'
import { startDebate, streamDebate } from '@/lib/api'
import type { Member } from '@/components/parliament/types'

type VoteMeta = {
  method?: string
  ranking?: string[]
}

export default function Page() {
  const [prompt, setPrompt] = useState('Draft a national EV policy')
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<any[]>([])
  const [activePersona, setActivePersona] = useState<string | undefined>(undefined)
  const [speakerTime, setSpeakerTime] = useState<number>(0)
  const [vote, setVote] = useState<VoteMeta | undefined>(undefined)
  const esRef = useRef<EventSource | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const members: Member[] = [
    { id: 'Analyst', name: 'Analyst', role: 'agent' },
    { id: 'Critic', name: 'Critic', role: 'critic' },
    { id: 'Builder', name: 'Builder', role: 'agent' },
    { id: 'JudgeAlpha', name: 'JudgeAlpha', role: 'judge' },
  ]

  const reset = () => {
    setEvents([])
    setActivePersona(undefined)
    setSpeakerTime(0)
    setVote(undefined)
  }

  const stopStream = () => {
    esRef.current?.close()
    esRef.current = null
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    setRunning(false)
  }

  const onStart = async () => {
    if (!prompt.trim()) return
    reset()
    setRunning(true)
    try {
      const { id } = await startDebate({ prompt })
      const es = streamDebate(id)
      esRef.current = es
      es.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          setEvents((prev) => [...prev, msg])
          if (msg.type === 'message') {
            const persona = msg.revised?.[0]?.persona ?? msg.candidates?.[0]?.persona
            if (persona) setActivePersona(persona)
          }
          if (msg.type === 'score' && Array.isArray(msg.scores)) {
            const ranking = [...msg.scores].sort((a: any, b: any) => b.score - a.score).map((s: any) => s.persona)
            setVote({ method: 'borda', ranking })
          }
          if (msg.type === 'final' && msg.meta?.ranking) {
            setVote({
              method: msg.meta?.vote?.method ?? 'borda',
              ranking: msg.meta.ranking,
            })
            stopStream()
          }
        } catch (error) {
          console.error('Failed to parse event', error)
        }
      }
      es.onerror = () => {
        stopStream()
      }
      timerRef.current = setInterval(() => setSpeakerTime((t) => t + 1), 1000)
    } catch (error) {
      console.error(error)
      stopStream()
    }
  }

  useEffect(() => {
    return () => {
      stopStream()
    }
  }, [])

  return (
    <main id="main" className="space-y-6 p-4">
      <Hero onStart={onStart} />
      <ParliamentChamber members={members} activeId={activePersona} speakerSeconds={speakerTime} />
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
      />
    </main>
  )
}
