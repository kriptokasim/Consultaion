"use client";

import { Activity, Download, Gavel, RefreshCcw, Terminal, Users } from "lucide-react";
import type { TimelineEvent } from "@/lib/timeline/types";
import type { SSEStatus } from "@/lib/sse";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n/client";

export type ArenaSeat = {
  id: string;
  name: string;
  role?: string;
  status?: "speaking" | "waiting" | "judge";
  tokens?: number;
  model?: string;
  provider?: string;
};

export type ArenaMetrics = {
  rounds?: number;
  tokensUsed?: number;
  elapsedSeconds?: number;
  updatedAt?: string;
  budgetReason?: string;
};

export type ArenaVoteStats = {
  aye: number;
  nay: number;
  threshold?: number;
};

export type ArenaRuntimeLog = {
  id: string;
  message: string;
  level?: "info" | "warn" | "error";
  at?: string;
};

interface DebateArenaProps {
  debate: any;
  events: TimelineEvent[];
  seats?: ArenaSeat[];
  metrics?: ArenaMetrics;
  voteStats?: ArenaVoteStats;
  logs?: ArenaRuntimeLog[];
  connectionStatus?: SSEStatus;
  reportUrl?: string;
}

const statusColors: Record<SSEStatus, string> = {
  idle: "bg-stone-200 text-stone-700",
  connecting: "bg-amber-100 text-amber-800",
  connected: "bg-emerald-100 text-emerald-800",
  reconnecting: "bg-rose-100 text-rose-700 animate-pulse",
  closed: "bg-stone-100 text-stone-700",
};

function formatTime(value?: string) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "—";
  return dt.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function formatDuration(seconds?: number) {
  if (!seconds || seconds <= 0) return "00:00";
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const secs = Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${mins}:${secs}`;
}

export default function DebateArena({
  debate,
  events,
  seats,
  metrics,
  voteStats,
  logs = [],
  connectionStatus = "idle",
  reportUrl,
}: DebateArenaProps) {
  const { t } = useI18n();
  const statusLabel: Record<SSEStatus, string> = {
    idle: t("arena.status.idle"),
    connecting: t("arena.status.connecting"),
    connected: t("arena.status.connected"),
    reconnecting: t("arena.status.reconnecting"),
    closed: t("arena.status.closed"),
  };

  const transcriptEvents = events.filter((event) =>
    ["message", "score", "final", "notice", "seat_message"].includes(event.type),
  );

  const voteTotals = {
    aye: voteStats?.aye ?? 0,
    nay: voteStats?.nay ?? 0,
  };
  const totalVotes = voteTotals.aye + voteTotals.nay;
  const ayePct = totalVotes > 0 ? (voteTotals.aye / totalVotes) * 100 : 0;
  const nayPct = totalVotes > 0 ? (voteTotals.nay / totalVotes) * 100 : 0;
  const logEntries = logs || [];

  return (
    <section className="font-sans">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-9 lg:gap-8">

        {/* Left Sidebar: Scoreboard */}
        <aside className="space-y-4 lg:col-span-3 lg:col-start-1">
          <div className="rounded-2xl border border-stone-200 bg-white/50 p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-stone-900">{t("arena.statusLabel")}</h2>
              <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider", statusColors[connectionStatus])}>
                {statusLabel[connectionStatus]}
              </span>
            </div>
            {/* Metrics */}
            <div className="rounded-2xl border border-amber-200/80 bg-white/90 p-4 shadow-sm mt-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-amber-900">
                <Activity className="h-4 w-4 text-amber-600" /> {t("arena.sessionMetrics")}
              </div>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <dt className="text-stone-500">{t("arena.metrics.rounds")}</dt>
                  <dd className="font-semibold text-stone-900">{metrics?.rounds ?? transcriptEvents.length}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-stone-500">{t("arena.metrics.tokens")}</dt>
                  <dd className="font-semibold text-stone-900">{metrics?.tokensUsed ? metrics.tokensUsed.toLocaleString() : "—"}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-stone-500">{t("arena.metrics.elapsed")}</dt>
                  <dd className="font-semibold text-stone-900">{formatDuration(metrics?.elapsedSeconds)}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-stone-500">{t("arena.metrics.updated")}</dt>
                  <dd className="font-semibold text-stone-900">{formatTime(metrics?.updatedAt)}</dd>
                </div>
                {metrics?.budgetReason ? (
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-rose-500">{t("arena.metrics.budget")}</dt>
                    <dd className="text-sm text-rose-600">{metrics.budgetReason}</dd>
                  </div>
                ) : null}
              </dl>

              <div className="mt-4 border-t pt-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-stone-900 mb-2">
                  <Terminal className="h-4 w-4 text-stone-500" /> Logs
                </div>
                <div className="space-y-2 text-[11px] font-mono overflow-y-auto max-h-48 pr-1">
                  {logEntries.length === 0 ? (
                    <p className="text-amber-200/80">Awaiting telemetry…</p>
                  ) : (
                    logEntries.map((log, idx) => (
                      <p
                        key={log.id || idx}
                        className={cn(
                          "whitespace-pre-wrap",
                          log.level === 'warn' && 'text-red-600',
                          log.level === 'error' && 'text-red-800 font-bold',
                          (!log.level || log.level === 'info') && 'text-stone-600'
                        )}
                      >
                        {[log.at ? `[${formatTime(log.at)}]` : null, log.message].filter(Boolean).join(' ')}
                      </p>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* Main Area: Transcript */}
        <section className="rounded-2xl border border-amber-200/80 bg-white/95 p-4 shadow-sm lg:col-span-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">{t("arena.hansard")}</p>
              <h3 className="text-lg font-semibold text-stone-900">{t("arena.hansard.subtitle")}</h3>
            </div>
            <span className="text-xs text-stone-500">{transcriptEvents.length} {t("arena.entriesLabel")}</span>
          </div>
          <div className="mt-4 space-y-3 max-h-[600px] overflow-y-auto pr-1">
            {transcriptEvents.length === 0 ? (
              <p className="text-sm text-stone-500">Awaiting debate events…</p>
            ) : (
              transcriptEvents.map((event, idx) => {
                const payload = event.payload || {};
                const isScore = event.type === 'score';
                const isNotice = event.type === 'notice';
                // Fallbacks
                const text = payload.text || payload.content || payload.message || "—";
                const actor = payload.seat_name || payload.actor || payload.seat_id || event.seat || "Member";
                const judge = payload.judge || "Judge";
                const score = payload.score;
                const rationale = payload.rationale;

                return (
                  <article key={event.id || `${event.type}-${idx}`} className="rounded-2xl border border-stone-100 bg-amber-50/40 px-4 py-3 shadow-inner">
                    <div className="flex items-center justify-between text-xs text-stone-500">
                      <span className="font-semibold text-stone-700">
                        {isScore ? judge : actor}
                      </span>
                      <span>{formatTime(event.ts)}</span>
                    </div>
                    <p className="mt-2 text-sm text-stone-800">
                      {isScore
                        ? `Score ${typeof score === 'number' ? score.toFixed(2) : score} for ${payload.persona || 'agent'}`
                        : text}
                    </p>
                    {isScore && rationale ? (
                      <p className="mt-2 text-xs text-stone-500">{rationale}</p>
                    ) : null}
                    {isNotice && text ? (
                      <p className="mt-2 text-xs text-amber-700">{text}</p>
                    ) : null}
                  </article>
                )
              })
            )}
          </div>
        </section>
      </div>
    </section>
  );
}
