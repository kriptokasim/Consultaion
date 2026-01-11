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
import { ErrorBanner } from "@/components/errors/ErrorBanner";
import { useI18n } from "@/lib/i18n/client";
import { trackEvent } from "@/lib/analytics";
import { ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import { useState } from "react";

type RunDetailClientProps = {
  id: string;
};

export default function RunDetailClient({ id }: RunDetailClientProps) {
  const { data: debate, isLoading, error, isProvisioning } = useDebate(id);
  const {
    events,
    addEvent,
    connectionStatus,
    setConnectionStatus,
    setActiveDebate,
    reset
  } = useDebateStore();
  const { t } = useI18n();
  const [showTechDetails, setShowTechDetails] = useState(false);

  // Reset store on mount/unmount
  useEffect(() => {
    setActiveDebate(id);
    return () => reset();
  }, [id, setActiveDebate, reset]);

  // Track provisioning telemetry
  useEffect(() => {
    if (isProvisioning) {
      trackEvent("debate_provisioning_start", { debateId: id });
    }
  }, [isProvisioning, id]);

  const base = DEFAULT_API_URL.replace(/\/$/, '');
  const streamUrl = `${base}/debates/${id}/stream`;
  const reportUrl = `${base}/debates/${id}/report`;
  const shouldStream = debate?.status === 'running' || debate?.status === 'queued';

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

  const { status: streamStatus, retryCount } = useEventSource<any>(shouldStream ? streamUrl : null, {
    enabled: !!shouldStream,
    withCredentials: true,
    onEvent: handleLiveEvent,
    onError: handleLiveError,
  });

  useEffect(() => {
    setConnectionStatus(streamStatus);
  }, [streamStatus, setConnectionStatus]);

  // Fallback Polling Logic (Patchset UX-92)
  const isSSEUnstable = streamStatus === 'reconnecting' && (retryCount || 0) > 2;
  const isSSEFailed = streamStatus === 'closed' && shouldStream; // or 'error' if we had that state
  const shouldPoll = shouldStream && (isSSEUnstable || isSSEFailed);

  useEffect(() => {
    if (!shouldPoll) return;

    const poll = async () => {
      try {
        const res = await fetch(`${base}/debates/${id}/timeline`);
        if (!res.ok) return;
        const data = await res.json();
        // We assume timeline returns the full list of events.
        // We need to diff or simply replace if the store allows.
        // For now, let's just feed new events if we can blindly add them (dedup logic is in store)
        if (Array.isArray(data)) {
          data.forEach(addEvent);
        }
      } catch (err) {
        console.error("Polling failed", err);
      }
    };

    const timer = setInterval(poll, 3000); // 3s polling
    return () => clearInterval(timer);
  }, [shouldPoll, base, id, addEvent]);

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

  const tokensUsed = debate?.final_meta?.usage?.total_tokens;

  const elapsedSeconds = useMemo(() => {
    if (!debate?.created_at || !debate?.updated_at) return undefined;
    const start = new Date(debate.created_at).getTime();
    const end = new Date(debate.updated_at).getTime();
    if (Number.isNaN(start) || Number.isNaN(end)) return undefined;
    return Math.max(0, Math.round((end - start) / 1000));
  }, [debate?.created_at, debate?.updated_at]);

  const seatDefinitions = useMemo(() => {
    if (debate?.panel_config?.seats && Array.isArray(debate.panel_config.seats) && debate.panel_config.seats.length) {
      return debate.panel_config.seats.map((seat: any) => ({
        id: seat.seat_id,
        name: seat.display_name,
        role: seat.role_profile === "judge" ? "judge" : seat.role_profile === "risk_officer" ? "critic" : "agent",
        provider: seat.provider_key,
        model: seat.model,
      }));
    }
    return DEFAULT_RUN_MEMBERS;
  }, [debate?.panel_config]);

  const arenaMetrics: ArenaMetrics = useMemo(
    () => ({
      rounds: events.filter((event) => event.type === 'message').length,
      tokensUsed,
      elapsedSeconds,
      updatedAt: debate?.updated_at,
      budgetReason: debate?.final_meta?.budget_reason,
    }),
    [debate?.final_meta?.budget_reason, debate?.updated_at, elapsedSeconds, events, tokensUsed]
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

  if (error && !isProvisioning) {
    throw error; // Let error boundary handle it
  }

  if (isLoading || isProvisioning) {
    return (
      <div className="flex h-screen flex-col items-center justify-center space-y-4">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-amber-200 border-t-amber-600" />
        <div className="text-center">
          <p className="text-lg font-semibold text-slate-800 dark:text-slate-200">
            {isProvisioning ? (t("dashboard.modal.provisioning") || "Creating debate...") : (t("dashboard.modal.loading") || "Loading debate...")}
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {isProvisioning ? "Provisioning AI agents..." : "Waiting for backend..."}
          </p>
        </div>
      </div>
    );
  }

  if (!debate) {
    notFound();
  }

  const createdAt = new Date(debate.created_at).toLocaleString();
  const updatedAt = new Date(debate.updated_at).toLocaleString();

  const status = (debate.status || "success").toLowerCase();
  const isDegraded = status === "degraded";
  const isFailed = status === "failed";

  const statusPillColor = isFailed
    ? "bg-red-100 text-red-800 border-red-200"
    : isDegraded
      ? "bg-amber-100 text-amber-800 border-amber-200"
      : "bg-emerald-100 text-emerald-800 border-emerald-200";

  const statusLabel = isFailed
    ? t("debate.status.failed")
    : isDegraded
      ? t("debate.status.degraded")
      : t("debate.status.success");

  // Track debate result state (Patchset 65.A5)
  useEffect(() => {
    if (debate) {
      trackEvent("debate_result_state", {
        debateId: id,
        status: status,
        hasErrors: (debate.participant_errors?.length ?? 0) > 0,
      });
    }
  }, [id, status, debate]);

  // Runtime logs (simplified for now, could be in store too)
  const runtimeLogs: ArenaRuntimeLog[] = [];

  return (
    <main id="main" className="space-y-6 p-4 lg:p-6">
      {(isDegraded || isFailed) && (
        <ErrorBanner
          type={isFailed ? "error" : "warning"}
          title={isFailed ? t("debate.failed.title") : t("debate.degraded.title")}
          message={isFailed ? t("debate.failed.message") : t("debate.degraded.message")}
        />
      )}
      <section className="rounded-3xl border border-amber-200/70 bg-gradient-to-br from-amber-50 via-white to-amber-50/70 p-6 shadow-[0_18px_40px_rgba(112,73,28,0.12)] dark:border-amber-900/40 dark:from-stone-900 dark:via-stone-900 dark:to-amber-950/20">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-700">Run detail</p>
        <h1 className="heading-serif text-2xl font-semibold text-amber-900 dark:text-amber-50">
          {debate.prompt ?? 'Parliament session'}
        </h1>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-amber-900/80 dark:text-amber-100/80">
          <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide shadow-inner shadow-amber-900/5 ${statusPillColor}`}>
            {statusLabel}
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
              {shouldPoll ? 'Polling (SSE unstable)' : connectionStatus === 'reconnecting' ? 'Reconnecting...' : 'Disconnected'}
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

      {(isDegraded || isFailed) && debate.participant_errors && debate.participant_errors.length > 0 && (
        <section className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
          <button
            onClick={() => setShowTechDetails(!showTechDetails)}
            className="flex w-full items-center justify-between text-sm font-semibold text-stone-700 hover:text-stone-900"
          >
            <span className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              {t("debate.technicalDetails.title")}
            </span>
            {showTechDetails ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>

          {showTechDetails && (
            <div className="mt-3 border-t border-stone-200 pt-3">
              <ul className="space-y-2 text-xs text-stone-600">
                {debate.participant_errors.map((err, idx) => (
                  <li key={err.id || idx} className="flex items-start gap-2">
                    <span className="font-mono font-medium text-stone-800">{err.role} ({err.name})</span>
                    <span className="text-stone-400">—</span>
                    <span className="font-mono text-red-700">{err.error_type}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
