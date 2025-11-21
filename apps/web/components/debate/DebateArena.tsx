'use client'

import { Activity, Download, Gavel, RefreshCcw, Terminal, Users } from "lucide-react";
import type { DebateEvent } from "@/components/parliament/types";
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
  budgetReason?: string | null;
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
  events: DebateEvent[];
  seats: ArenaSeat[];
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
  logs,
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
  ).slice(-24);

  const voteTotals = {
    aye: voteStats?.aye ?? 0,
    nay: voteStats?.nay ?? 0,
  };
  const totalVotes = Math.max(1, voteTotals.aye + voteTotals.nay || 1);
  const ayePct = Math.round((voteTotals.aye / totalVotes) * 100);
  const nayPct = Math.round((voteTotals.nay / totalVotes) * 100);

  const logEntries = (logs ?? []).slice(-12);
  const resolvedSeats = seats.length
    ? seats
    : [
        { id: "analyst", name: "Analyst", role: "agent", status: "speaking", tokens: 0, provider: undefined, model: undefined },
        { id: "critic", name: "Critic", role: "critic", status: "waiting", tokens: 0, provider: undefined, model: undefined },
      ];

  return (
    <section className="rounded-3xl border border-amber-200/70 bg-gradient-to-br from-amber-50 via-white to-amber-50/50 p-6 shadow-[0_18px_40px_rgba(112,73,28,0.12)]">
      <div className="flex flex-col gap-4 border-b border-amber-200/70 pb-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-700">{t("arena.title")}</p>
          <h2 className="heading-serif text-2xl font-semibold text-stone-900">{debate?.prompt ?? t("arena.title")}</h2>
          <p className="mt-2 text-sm text-stone-600">
            Session #{debate?.id ?? "—"} · Status {debate?.status ?? "unknown"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={cn("inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold", statusColors[connectionStatus])}>
            <RefreshCcw className="h-3.5 w-3.5" />
            {statusLabel[connectionStatus]}
          </span>
          {reportUrl ? (
            <a
              className="inline-flex items-center gap-2 rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-semibold text-amber-900 shadow-sm hover:bg-amber-50"
              href={reportUrl}
              target="_blank"
              rel="noreferrer"
            >
              <Download className="h-3.5 w-3.5" /> Transcript
            </a>
          ) : null}
        </div>
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-12">
        <aside className="space-y-4 lg:col-span-3">
          <div className="rounded-2xl border border-amber-200/80 bg-white/90 p-4 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-semibold text-amber-900">
              <Users className="h-4 w-4 text-amber-600" /> {t("arena.activeSeats")}
            </div>
            <div className="mt-3 space-y-2">
              {resolvedSeats.map((seat) => (
                <div
                  key={seat.id}
                  className={cn(
                    "flex items-center justify-between rounded-xl border px-3 py-2",
                    seat.status === "speaking"
                      ? "border-amber-400 bg-amber-50"
                      : "border-amber-100 bg-white",
                  )}
                >
                  <div>
                    <p className="text-sm font-semibold text-stone-900">{seat.name}</p>
                    <p className="text-[11px] uppercase tracking-wide text-stone-500">
                      {seat.role ?? "agent"}
                      {seat.provider ? ` · ${seat.provider}` : null}
                    </p>
                    {seat.model ? <p className="text-[11px] text-stone-400">{seat.model}</p> : null}
                  </div>
                  <div className="text-right text-[11px] text-stone-600">
                    {seat.tokens !== undefined ? (
                      <p className="font-mono text-sm text-stone-900">{seat.tokens.toLocaleString()}</p>
                    ) : null}
                    <p className="capitalize text-xs text-stone-500">{seat.status ?? "waiting"}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-amber-200/80 bg-white/90 p-4 shadow-sm">
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
          </div>
        </aside>

        <section className="rounded-2xl border border-amber-200/80 bg-white/95 p-4 shadow-sm lg:col-span-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">{t("arena.hansard")}</p>
              <h3 className="text-lg font-semibold text-stone-900">{t("arena.hansard.subtitle")}</h3>
            </div>
            <span className="text-xs text-stone-500">{transcriptEvents.length} {t("arena.entriesLabel")}</span>
          </div>
          <div className="mt-4 space-y-3 max-h-[420px] overflow-y-auto pr-1">
            {transcriptEvents.length === 0 ? (
              <p className="text-sm text-stone-500">Awaiting debate events…</p>
            ) : (
              transcriptEvents.map((event, idx) => (
                <article key={`${event.type}-${idx}`} className="rounded-2xl border border-stone-100 bg-amber-50/40 px-4 py-3 shadow-inner">
                  <div className="flex items-center justify-between text-xs text-stone-500">
                    <span className="font-semibold text-stone-700">
                      {(() => {
                        if (event.type === 'score') return event.judge ?? 'Judge'
                        if ('actor' in event && event.actor) return event.actor
                        if ('seatId' in event && event.seatId) return event.seatId
                        return 'Member'
                      })()}
                    </span>
                    <span>{formatTime(event.at)}</span>
                  </div>
                  <p className="mt-2 text-sm text-stone-800">
                    {event.type === 'score'
                      ? `Score ${typeof event.score === 'number' ? event.score.toFixed(2) : event.score} for ${event.persona ?? 'agent'}`
                      : 'text' in event && event.text
                        ? event.text
                        : '—'}
                  </p>
                  {event.type === 'score' && event.rationale ? (
                    <p className="mt-2 text-xs text-stone-500">{event.rationale}</p>
                  ) : null}
                  {event.type === 'notice' && event.text ? (
                    <p className="mt-2 text-xs text-amber-700">{event.text}</p>
                  ) : null}
                </article>
              ))
            )}
          </div>
        </section>

        <aside className="space-y-4 lg:col-span-3">
          <div className="rounded-2xl border border-amber-200/80 bg-white/95 p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-amber-900">
                <Gavel className="h-4 w-4 text-amber-600" /> {t("arena.votingChamber")}
              </div>
              {voteStats?.threshold ? (
                <span className="text-[11px] font-semibold uppercase tracking-wide text-stone-500">
                  {t("arena.votes.threshold")} {voteStats.threshold}
                </span>
              ) : null}
            </div>
            <div className="mt-4 space-y-3 text-sm">
              <div>
                <div className="flex justify-between text-xs text-stone-500">
                  <span>Aye</span>
                  <span className="font-mono text-amber-900">{voteTotals.aye}</span>
                </div>
                <div className="mt-1 h-2 rounded-full bg-amber-100">
                  <div className="h-full rounded-full bg-emerald-500" style={{ width: `${ayePct}%` }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs text-stone-500">
                  <span>Nay</span>
                  <span className="font-mono text-amber-900">{voteTotals.nay}</span>
                </div>
                <div className="mt-1 h-2 rounded-full bg-amber-100">
                  <div className="h-full rounded-full bg-rose-500" style={{ width: `${nayPct}%` }} />
                </div>
              </div>
            </div>
          </div>
          <div className="rounded-2xl border border-stone-900/40 bg-[#0c0a09] p-4 shadow-lg shadow-black/50 text-amber-50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Terminal className="h-4 w-4 text-amber-400" /> {t("arena.runtimeLogs")}
              </div>
              <span className="text-[10px] text-amber-200">last {logEntries.length} events</span>
            </div>
            <div className="mt-3 space-y-2 text-[11px] font-mono overflow-y-auto max-h-48 pr-1">
              {logEntries.length === 0 ? (
                <p className="text-amber-200/80">Awaiting telemetry…</p>
              ) : (
                logEntries.map((log) => (
                  <p
                    key={log.id}
                    className={cn(
                      "whitespace-pre-wrap",
                      log.level === 'warn' && 'text-rose-200',
                      log.level === 'error' && 'text-red-300',
                    )}
                  >
                    {[log.at ? `[${formatTime(log.at)}]` : null, log.message].filter(Boolean).join(' ')}
                  </p>
                ))
              )}
            </div>
          </div>
        </aside>
      </div>
    </section>
  )
}
