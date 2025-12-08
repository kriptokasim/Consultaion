'use client';

import { useCallback, useEffect, useMemo } from "react";
import DebateArena, {
  type ArenaMetrics,
  type ArenaRuntimeLog,
  type ArenaSeat,
} from "@/components/debate/DebateArena";
import ParliamentRunView from "@/components/parliament/ParliamentRunView";
import type {
  Member,
  ScoreItem,
  VotePayload,
} from "@/components/parliament/types";
import { useEventSource } from "@/lib/sse";
import { useDebate } from "@/lib/api/hooks/useDebate";
import { useDebateStore } from "@/lib/stores/debateStore";
import { notFound } from "next/navigation";
import { normalizeLivePayload } from "@/lib/debateTransforms";
import { DEFAULT_RUN_MEMBERS, DEFAULT_API_URL, DEFAULT_VOTE_THRESHOLD } from "@/config/debateDefaults";
import { useDebateVoting } from "@/hooks/useDebateVoting";

type RunDetailClientProps = {
  id: string;
};

export default function RunDetailClient({ id }: RunDetailClientProps) {
  const { data: debate, isLoading, error } = useDebate(id);
  const {
    events,
    addEvent,
    connectionStatus,
    setConnectionStatus,
    setActiveDebate,
    reset
  } = useDebateStore();

  // Reset store on mount/unmount
  useEffect(() => {
    setActiveDebate(id);
    return () => reset();
  }, [id, setActiveDebate, reset]);

  if (error) {
    throw error; // Let error boundary handle it
  }

  if (isLoading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>;
  }

  if (!debate) {
    notFound();
  }

  const base = DEFAULT_API_URL.replace(/\/$/, '');
  const streamUrl = `${base}/debates/${id}/stream`;
  const reportUrl = `${base}/debates/${id}/report`;
  const shouldStream = debate.status === 'running' || debate.status === 'queued';

  const handleLiveEvent = useCallback(
    (payload: any) => {
      const now = new Date().toISOString();
      const normalized = normalizeLivePayload(payload, now);
      if (normalized.length) {
        normalized.forEach(addEvent);
      }
    },
    [addEvent]
  );

  const handleLiveError = useCallback(() => {
    // handled by sse hook status
  }, []);

  const { status: streamStatus } = useEventSource<any>(shouldStream ? streamUrl : null, {
    enabled: shouldStream,
    withCredentials: true,
    onEvent: handleLiveEvent,
    onError: handleLiveError,
  });

  useEffect(() => {
    setConnectionStatus(streamStatus);
  }, [streamStatus, setConnectionStatus]);

  // Use the extracted voting hook
  const { eventScores, judgeVotes, voteBasis, voteStats } = useDebateVoting({
    events,
    threshold: DEFAULT_VOTE_THRESHOLD
  });

  const aggregatedScores: ScoreItem[] = useMemo(() => {
    if (!eventScores.length) return [];
    const table = new Map<string, any[]>();
    for (const entry of eventScores) {
      const list = table.get(entry.persona) ?? [];
      list.push(entry);
      table.set(entry.persona, list);
    }
    return Array.from(table.entries()).map(([persona, entries]) => {
      const total = entries.reduce((sum, entry) => sum + entry.score, 0);
      const avg = entries.length ? total / entries.length : 0;
      const last = entries[entries.length - 1];
      return {
        persona,
        score: Number(avg.toFixed(2)),
        rationale: last?.rationale,
      };
    });
  }, [eventScores]);

  const scores = aggregatedScores;

  const ranking = scores.length ? [...scores].sort((a, b) => b.score - a.score).map((s) => s.persona) : [];
  const vote: VotePayload | undefined = ranking.length ? { method: 'borda', ranking } : undefined;

  const latestSpeaker = useMemo(() => {
    const reversed = [...events].reverse();
    const messageEvent = reversed.find((event) => event.type === 'message');
    return messageEvent?.actor;
  }, [events]);

  const tokensUsed = typeof debate.final_meta?.usage?.total_tokens === 'number'
    ? debate.final_meta.usage.total_tokens
    : undefined;

  const elapsedSeconds = useMemo(() => {
    if (!debate.created_at || !debate.updated_at) return undefined;
    const start = new Date(debate.created_at).getTime();
    const end = new Date(debate.updated_at).getTime();
    if (Number.isNaN(start) || Number.isNaN(end)) return undefined;
    return Math.max(0, Math.round((end - start) / 1000));
  }, [debate.created_at, debate.updated_at]);

  const seatDefinitions = useMemo(() => {
    if (Array.isArray(debate.panel_config?.seats) && debate.panel_config.seats.length) {
      return debate.panel_config.seats.map((seat: any) => ({
        id: seat.seat_id,
        name: seat.display_name,
        role: seat.role_profile === "judge" ? "judge" : seat.role_profile === "risk_officer" ? "critic" : "agent",
        provider: seat.provider_key,
        model: seat.model,
      }));
    }
    return DEFAULT_RUN_MEMBERS;
  }, [debate.panel_config]);

  const arenaMetrics: ArenaMetrics = useMemo(
    () => ({
      rounds: events.filter((event) => event.type === 'message').length,
      tokensUsed,
      elapsedSeconds,
      updatedAt: debate.updated_at,
      budgetReason: debate.final_meta?.budget_reason,
    }),
    [debate.final_meta?.budget_reason, debate.updated_at, elapsedSeconds, events, tokensUsed]
  );

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
    [seatDefinitions, latestSpeaker, tokensUsed]
  );

  const createdAt = new Date(debate.created_at).toLocaleString();
  const updatedAt = new Date(debate.updated_at).toLocaleString();

  // Runtime logs (simplified for now, could be in store too)
  const runtimeLogs: ArenaRuntimeLog[] = [];

  return (
    <main id="main" className="space-y-6 p-4 lg:p-6">
      <section className="rounded-3xl border border-amber-200/70 bg-gradient-to-br from-amber-50 via-white to-amber-50/70 p-6 shadow-[0_18px_40px_rgba(112,73,28,0.12)] dark:border-amber-900/40 dark:from-stone-900 dark:via-stone-900 dark:to-amber-950/20">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-700">Run detail</p>
        <h1 className="heading-serif text-2xl font-semibold text-amber-900 dark:text-amber-50">
          {debate.prompt ?? 'Parliament session'}
        </h1>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-amber-900/80 dark:text-amber-100/80">
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-200/80 bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-800 shadow-inner shadow-amber-900/5 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
            Status: {debate.status}
          </span>
          {debate.model_id ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-amber-200/80 bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-800 shadow-inner shadow-amber-900/5 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
              Model: {debate.model_id}
            </span>
          ) : null}
          <span>Created {createdAt}</span>
          <span>Updated {updatedAt}</span>
          {connectionStatus !== 'idle' && connectionStatus !== 'connected' && (
            <span className="text-amber-600 font-bold animate-pulse">
              {connectionStatus === 'reconnecting' ? 'Reconnecting...' : 'Disconnected'}
            </span>
          )}
        </div>
      </section>

      <DebateArena
        debate={debate}
        events={events}
        seats={arenaSeats}
        metrics={arenaMetrics}
        voteStats={voteStats}
        logs={runtimeLogs}
        connectionStatus={connectionStatus}
        reportUrl={reportUrl}
      />

      <ParliamentRunView
        id={id}
        debate={debate}
        scores={scores}
        vote={vote}
        events={events}
        members={DEFAULT_RUN_MEMBERS}
        judgeVotes={judgeVotes}
        threshold={DEFAULT_VOTE_THRESHOLD}
        voteBasis={voteBasis}
        apiBase={base}
      />
    </main>
  );
}
