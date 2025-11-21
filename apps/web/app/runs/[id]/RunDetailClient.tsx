'use client'

import { useCallback, useEffect, useMemo, useState } from "react";
import DebateArena, {
  type ArenaMetrics,
  type ArenaRuntimeLog,
  type ArenaSeat,
  type ArenaVoteStats,
} from "@/components/debate/DebateArena";
import ParliamentRunView from "@/components/parliament/ParliamentRunView";
import type {
  DebateEvent,
  JudgeScoreEvent,
  Member,
  PairwiseEvent,
  JudgeVoteFlow,
  ScoreItem,
  VotePayload,
} from "@/components/parliament/types";
import { useEventSource } from "@/lib/sse";

type RunDetailClientProps = {
  id: string;
  initialDebate: any;
  initialReport: any;
  initialEvents: DebateEvent[];
  initialMembers: Member[];
  threshold: number;
  apiBase: string;
};

const DEFAULT_API = "http://localhost:8000";
const DEFAULT_RUN_MEMBERS: Member[] = [
  { id: "Analyst", name: "Analyst", role: "agent" },
  { id: "Critic", name: "Critic", role: "critic" },
  { id: "Builder", name: "Builder", role: "agent" },
];

function normalizeLivePayload(payload: any, timestamp: string): DebateEvent[] {
  if (!payload || typeof payload !== "object") return [];
  const type = payload.type;
  if (type === "seat_message") {
    if (!payload.content) return []
    return [
      {
        type: "message" as const,
        actor: payload.seat_name ?? payload.seat_id ?? "Seat",
        role: "agent",
        text: payload.content,
        at: timestamp,
        provider: payload.provider,
        model: payload.model,
        seatId: payload.seat_id,
      },
    ]
  }
  if (type === "message") {
    const entries = Array.isArray(payload.revised) && payload.revised.length
      ? payload.revised
      : Array.isArray(payload.candidates)
        ? payload.candidates
        : [];
    return entries
      .filter((entry: any) => entry && entry.text)
      .map((entry: any) => ({
        type: "message" as const,
        actor: entry.persona ?? entry.role ?? payload.actor,
        role: "agent",
        text: entry.text,
        at: timestamp,
      }));
  }
  if (type === "score") {
    if (Array.isArray(payload.judges) && payload.judges.length) {
      return payload.judges.map((judge: any) => ({
        type: "score" as const,
        persona: judge.persona,
        judge: judge.judge ?? "Panel",
        score: typeof judge.score === "number" ? judge.score : Number(judge.score ?? 0),
        rationale: judge.rationale,
        at: timestamp,
        role: "judge",
      }));
    }
    if (Array.isArray(payload.scores)) {
      return payload.scores.map((score: any) => ({
        type: "score" as const,
        persona: score.persona,
        judge: payload.actor ?? "Panel",
        score: typeof score.score === "number" ? score.score : Number(score.score ?? 0),
        rationale: score.rationale,
        at: timestamp,
        role: "judge",
      }));
    }
  }
  if (type === "final") {
    return [
      {
        type: "final" as const,
        actor: payload.actor ?? "Synthesizer",
        role: "synthesizer",
        text: payload.content ?? payload.meta?.final_content ?? "",
        at: timestamp,
      },
    ];
  }
  if (type === "notice" || type === "error" || type === "round_started") {
    const message =
      payload.message ??
      payload.detail ??
      (type === "round_started" ? `Round ${payload.round ?? ''} started` : undefined);
    if (!message) return [];
    return [
      {
        type: "notice" as const,
        text: message,
        at: timestamp,
        role: "judge",
      },
    ];
  }
  return [];
}

export default function RunDetailClient({
  id,
  initialDebate,
  initialReport,
  initialEvents,
  initialMembers,
  threshold,
  apiBase,
}: RunDetailClientProps) {
  const [debate, setDebate] = useState(initialDebate)
  const [events, setEvents] = useState<DebateEvent[]>(initialEvents)
  const [runtimeLogs, setRuntimeLogs] = useState<ArenaRuntimeLog[]>([])
  const baseMembers = initialMembers.length ? initialMembers : DEFAULT_RUN_MEMBERS
  const panelMembers = Array.isArray(initialDebate?.panel_config?.seats)
    ? initialDebate.panel_config.seats.map((seat: any) => ({
        id: seat.seat_id,
        name: seat.display_name,
        role: seat.role_profile === "judge" ? "judge" : seat.role_profile === "risk_officer" ? "critic" : "agent",
        party: seat.provider_key,
      }))
    : null
  const members = panelMembers ?? baseMembers

  const base = (apiBase || DEFAULT_API).replace(/\/$/, '')
  const streamUrl = `${base}/debates/${id}/stream`
  const reportUrl = `${base}/debates/${id}/report`
  const shouldStream = Boolean(debate) && (debate?.status === 'running' || debate?.status === 'queued')

  const appendLog = useCallback((entry: ArenaRuntimeLog) => {
    setRuntimeLogs((prev) => [...prev.slice(-20), entry])
  }, [])

  const handleLiveEvent = useCallback(
    (payload: any) => {
      const now = new Date().toISOString()
      appendLog({ id: `log-${now}`, message: `Event: ${payload?.type ?? 'sse'}`, at: now, level: payload?.type === 'error' ? 'warn' : 'info' })
      const normalized = normalizeLivePayload(payload, now)
      if (normalized.length) {
        setEvents((prev) => [...prev, ...normalized])
      }
      if (payload?.type === 'final') {
        setDebate((prev: any) =>
          prev
            ? {
                ...prev,
                status: 'completed',
                final_content: payload.content ?? prev.final_content,
                final_meta: payload.meta ?? prev.final_meta,
              }
            : prev,
        )
      }
    },
    [appendLog],
  )

  const handleLiveError = useCallback(() => {
    const now = new Date().toISOString()
    appendLog({ id: `err-${now}`, message: 'SSE connection interrupted', at: now, level: 'warn' })
  }, [appendLog])

  const { status: streamStatus } = useEventSource<any>(shouldStream ? streamUrl : null, {
    enabled: shouldStream,
    withCredentials: true,
    onEvent: handleLiveEvent,
    onError: handleLiveError,
  })

  useEffect(() => {
    if (streamStatus === 'reconnecting') {
      const at = new Date().toISOString()
      appendLog({ id: `reconnect-${at}`, message: 'Attempting to reconnect…', at, level: 'warn' })
    }
  }, [streamStatus, appendLog])

  const eventScores = useMemo(
    () => events.filter((event): event is JudgeScoreEvent => event.type === 'score'),
    [events],
  )

  const aggregatedScores: ScoreItem[] = useMemo(() => {
    if (!eventScores.length) return []
    const table = new Map<string, JudgeScoreEvent[]>()
    for (const entry of eventScores) {
      const list = table.get(entry.persona) ?? []
      list.push(entry)
      table.set(entry.persona, list)
    }
    return Array.from(table.entries()).map(([persona, entries]) => {
      const total = entries.reduce((sum, entry) => sum + entry.score, 0)
      const avg = entries.length ? total / entries.length : 0
      const last = entries[entries.length - 1]
      return {
        persona,
        score: Number(avg.toFixed(2)),
        rationale: last?.rationale,
      }
    })
  }, [eventScores])

  const fallbackScores: ScoreItem[] = useMemo(() => {
    const reportScores = Array.isArray(initialReport?.scores) ? initialReport.scores : []
    return reportScores.map((entry: any) => ({
      persona: entry.persona ?? 'Agent',
      score: typeof entry.score === 'number' ? entry.score : Number(entry.score ?? 0),
      rationale: entry.rationale,
    }))
  }, [initialReport])

  const scores = aggregatedScores.length ? aggregatedScores : fallbackScores

  const ranking = scores.length ? [...scores].sort((a, b) => b.score - a.score).map((s) => s.persona) : []
  const vote: VotePayload | undefined = ranking.length ? { method: 'borda', ranking } : undefined

  const pairwiseEvents = useMemo(
    () => events.filter((event): event is PairwiseEvent => event.type === 'pairwise'),
    [events],
  )

  const judgeVotes: JudgeVoteFlow[] = useMemo(() => {
    if (pairwiseEvents.length) {
      return pairwiseEvents.map((entry) => ({
        persona: entry.winner,
        judge: entry.judge ?? 'division',
        score: 1,
        at: entry.at,
        vote: 'aye' as const,
      }))
    }
    return eventScores.map((entry) => ({
      persona: entry.persona,
      judge: entry.judge,
      score: entry.score,
      at: entry.at,
      vote: entry.score >= threshold ? ('aye' as const) : ('nay' as const),
    }))
  }, [eventScores, pairwiseEvents, threshold])

  const voteBasis: 'pairwise' | 'threshold' = pairwiseEvents.length ? 'pairwise' : 'threshold'

  const voteStats: ArenaVoteStats = useMemo(
    () => ({
      aye: judgeVotes.filter((entry) => entry.vote === 'aye').length,
      nay: judgeVotes.filter((entry) => entry.vote === 'nay').length,
      threshold,
    }),
    [judgeVotes, threshold],
  )

  const latestSpeaker = useMemo(() => {
    const reversed = [...events].reverse()
    const messageEvent = reversed.find((event) => event.type === 'message')
    return messageEvent?.actor
  }, [events])

  const tokensUsed = typeof debate?.final_meta?.usage?.total_tokens === 'number'
    ? debate.final_meta.usage.total_tokens
    : undefined

  const elapsedSeconds = useMemo(() => {
    if (!debate?.created_at || !debate?.updated_at) return undefined
    const start = new Date(debate.created_at).getTime()
    const end = new Date(debate.updated_at).getTime()
    if (Number.isNaN(start) || Number.isNaN(end)) return undefined
    return Math.max(0, Math.round((end - start) / 1000))
  }, [debate?.created_at, debate?.updated_at])

  const seatDefinitions = useMemo(() => {
    if (Array.isArray(debate?.panel_config?.seats) && debate.panel_config.seats.length) {
      return debate.panel_config.seats.map((seat: any) => ({
        id: seat.seat_id,
        name: seat.display_name,
        role: seat.role_profile === "judge" ? "judge" : seat.role_profile === "risk_officer" ? "critic" : "agent",
        provider: seat.provider_key,
        model: seat.model,
      }))
    }
    return members.map((member: Member) => ({
      id: member.id,
      name: member.name,
      role: member.role,
      provider: member.party,
    }))
  }, [debate?.panel_config, members])

  const arenaMetrics: ArenaMetrics = useMemo(
    () => ({
      rounds: events.filter((event) => event.type === 'message').length,
      tokensUsed,
      elapsedSeconds,
      updatedAt: debate?.updated_at,
      budgetReason: debate?.final_meta?.budget_reason,
    }),
    [debate?.final_meta?.budget_reason, debate?.updated_at, elapsedSeconds, events, tokensUsed],
  )

  const arenaSeats: ArenaSeat[] = useMemo(
    () =>
      seatDefinitions.map((seat: { id: string; name: string; role: string; provider?: string; model?: string }) => ({
        id: seat.id,
        name: seat.name,
        role: seat.role,
        provider: seat.provider,
        model: seat.model,
        status: seat.role === 'judge' ? 'judge' : seat.name === latestSpeaker ? 'speaking' : 'waiting',
        tokens: tokensUsed ? Math.max(1, Math.round(tokensUsed / Math.max(1, seatDefinitions.length))) : undefined,
      })),
    [seatDefinitions, latestSpeaker, tokensUsed],
  )

  const createdAt =
    debate?.created_at && typeof debate.created_at === 'string'
      ? new Date(debate.created_at).toLocaleString()
      : undefined
  const updatedAt =
    debate?.updated_at && typeof debate.updated_at === 'string'
      ? new Date(debate.updated_at).toLocaleString()
      : undefined

  return (
    <main id="main" className="space-y-6 p-4 lg:p-6">
      <section className="rounded-3xl border border-amber-200/70 bg-gradient-to-br from-amber-50 via-white to-amber-50/70 p-6 shadow-[0_18px_40px_rgba(112,73,28,0.12)] dark:border-amber-900/40 dark:from-stone-900 dark:via-stone-900 dark:to-amber-950/20">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-700">Run detail</p>
        <h1 className="heading-serif text-2xl font-semibold text-amber-900 dark:text-amber-50">
          {debate?.prompt ?? 'Parliament session'}
        </h1>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-amber-900/80 dark:text-amber-100/80">
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-200/80 bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-800 shadow-inner shadow-amber-900/5 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
            Status: {debate?.status ?? 'queued'}
          </span>
          {debate?.model_id ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-amber-200/80 bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-800 shadow-inner shadow-amber-900/5 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
              Model: {debate.model_id}
            </span>
          ) : null}
          {createdAt ? <span>Created {createdAt}</span> : null}
          {updatedAt ? <span>Updated {updatedAt}</span> : null}
        </div>
      </section>

      <DebateArena
        debate={debate}
        events={events}
        seats={arenaSeats}
        metrics={arenaMetrics}
        voteStats={voteStats}
        logs={runtimeLogs}
        connectionStatus={streamStatus}
        reportUrl={reportUrl}
      />

      <ParliamentRunView
        id={id}
        debate={debate}
        scores={scores}
        vote={vote}
        events={events}
        members={members}
        judgeVotes={judgeVotes}
        threshold={threshold}
        voteBasis={voteBasis}
        apiBase={base || DEFAULT_API}
      />
    </main>
  )
}
