'use client'

import { useEffect, useRef, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const CONFIG_SCHEMA_TEMPLATE = {
  agents: [
    { name: 'Analyst', persona: 'Systems thinker focused on trade-offs.', model: 'openai/gpt-4o-mini' }
  ],
  judges: [
    { name: 'JudgeAlpha', model: 'openai/gpt-4o-mini', rubrics: ['accuracy', 'completeness'] }
  ],
  budget: { max_tokens: 60000, max_cost_usd: 1.5, early_stop_delta: 1 }
}

const CONFIG_SCHEMA_SAMPLE = JSON.stringify(CONFIG_SCHEMA_TEMPLATE, null, 2)

function validateConfig(config: unknown) {
  if (typeof config !== 'object' || config === null) {
    throw new Error('Configuration must be a JSON object')
  }
  const obj = config as Record<string, any>
  if (!Array.isArray(obj.agents) || obj.agents.length === 0) {
    throw new Error('Config requires a non-empty "agents" array')
  }
  if (!Array.isArray(obj.judges) || obj.judges.length === 0) {
    throw new Error('Config requires a non-empty "judges" array')
  }
  obj.agents.forEach((agent, idx) => {
    if (!agent.name || !agent.persona) {
      throw new Error(`Agent #${idx + 1} missing name or persona`)
    }
  })
  obj.judges.forEach((judge, idx) => {
    if (!judge.name) {
      throw new Error(`Judge #${idx + 1} missing name`)
    }
    if (judge.rubrics && !Array.isArray(judge.rubrics)) {
      throw new Error(`Judge #${idx + 1} rubrics must be an array`)
    }
  })
  return obj
}

type EventMsg = {
  type: string
  [k: string]: unknown
}

export default function Home() {
  const [prompt, setPrompt] = useState('Propose a sustainable transport strategy for a new city.')
  const [log, setLog] = useState<string[]>([])
  const [configText, setConfigText] = useState('')
  const [customConfig, setCustomConfig] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [currentRound, setCurrentRound] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)
  const runningRef = useRef(false)

  useEffect(() => {
    const loadDefaultConfig = async () => {
      try {
        const res = await fetch(`${API}/config/default`)
        if (!res.ok) return
        const data = await res.json()
        setConfigText(JSON.stringify(data, null, 2))
      } catch {
        // ignore fetch errors; user can still type config manually
      }
    }
    loadDefaultConfig()

    return () => {
      if (esRef.current) esRef.current.close()
    }
  }, [])

  const attachStream = (id: string, attempt = 0) => {
    if (esRef.current) esRef.current.close()
    const es = new EventSource(`${API}/debates/${id}/stream`)
    esRef.current = es

    es.onmessage = (e) => {
      try {
        const msg: EventMsg = JSON.parse(e.data)
        if (msg.type === 'round_started') {
          setCurrentRound(msg.note || `Round ${msg.round}`)
        }
        setLog((prev) => [...prev, JSON.stringify(msg, null, 2)])
        if (msg.type === 'final' || msg.type === 'error') {
          es.close()
          runningRef.current = false
          setIsRunning(false)
          setCurrentRound(null)
        }
      } catch (err) {
        console.error('Failed to parse event', err)
      }
    }

    es.onerror = () => {
      es.close()
      if (!runningRef.current) return
      const nextAttempt = attempt + 1
      const delay = Math.min(30000, 1000 * 2 ** nextAttempt)
      setTimeout(() => attachStream(id, nextAttempt), delay)
    }
  }

  const run = async () => {
    setLog([])
    setError(null)
    setCurrentRound(null)

    const payload: Record<string, unknown> = { prompt }
    if (customConfig && configText.trim()) {
      try {
        const parsed = JSON.parse(configText)
        payload.config = validateConfig(parsed)
      } catch (err) {
        setError((err as Error).message || 'Configuration JSON is invalid.')
        return
      }
    }

    const r = await fetch(`${API}/debates`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!r.ok) {
      setError('Failed to start debate. Check API logs.')
      return
    }
    const { id } = await r.json()

    setIsRunning(true)
    runningRef.current = true
    attachStream(id)
  }

  return (
    <main className="max-w-3xl mx-auto p-6 space-y-4">
      <h1 className="text-3xl font-bold">Consultaion</h1>
      <p className="text-sm text-slate-600">Produce the best answer via multi-agent deliberation.</p>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        className="w-full h-40 p-3 border rounded"
      />

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={customConfig} onChange={(e) => setCustomConfig(e.target.checked)} />
        Use custom agent/judge configuration
      </label>

      {customConfig ? (
        <div className="grid gap-4 md:grid-cols-2">
          <textarea
            value={configText}
            onChange={(e) => setConfigText(e.target.value)}
            className="w-full h-48 p-3 border rounded font-mono text-xs"
          />
          <pre className="w-full h-48 p-3 border rounded font-mono text-xs bg-slate-50 overflow-auto">
            {CONFIG_SCHEMA_SAMPLE}
          </pre>
        </div>
      ) : null}

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <button
        onClick={run}
        disabled={isRunning}
        className={`px-4 py-2 rounded text-white ${isRunning ? 'bg-gray-500 cursor-not-allowed' : 'bg-black'}`}
      >
        {isRunning ? 'Running…' : 'Run'}
      </button>

      <a href="/runs" className="text-sm text-blue-600 underline">
        View run history →
      </a>

      {isRunning && currentRound ? (
        <p className="text-sm text-slate-700">Current round: {currentRound}</p>
      ) : null}

      <div className="mt-6 grid gap-2">
        {log.map((entry, idx) => (
          <pre key={idx} className="bg-white border rounded p-3 overflow-auto text-xs">
            {entry}
          </pre>
        ))}
      </div>
    </main>
  )
}
