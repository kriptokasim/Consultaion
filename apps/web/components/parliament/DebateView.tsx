"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MessageSquare } from "lucide-react";
import { useI18n } from "@/lib/i18n/client";
import type { DebateEvent, Role } from "./types";
import { formatEventType, formatModelLabel } from "@/lib/ui/formatters";

export interface DebateViewProps {
  events: DebateEvent[];
  className?: string;
  /** When true, the inner title/heading is suppressed because a parent card already provides one. */
  embedded?: boolean;
}

const ROLE_COLORS: Record<Role, { border: string; dot: string }> = {
  agent: {
    border: "border-l-blue-300 dark:border-l-blue-500",
    dot: "bg-blue-500",
  },
  critic: {
    border: "border-l-purple-300 dark:border-l-purple-500",
    dot: "bg-purple-500",
  },
  judge: {
    border: "border-l-amber-400 dark:border-l-amber-500",
    dot: "bg-amber-500",
  },
  synthesizer: {
    border: "border-l-emerald-300 dark:border-l-emerald-500",
    dot: "bg-emerald-500",
  },
};

const getRoleColors = (role?: Role) => {
  if (role && ROLE_COLORS[role]) return ROLE_COLORS[role];
  return { border: "border-l-border", dot: "bg-muted-foreground/30" };
};

const getTypeBadge = (type: string) => {
  const badges: Record<string, string> = {
    message: "bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800",
    seat_message: "bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800",
    score: "bg-accent-secondary/10 text-accent-secondary border-accent-secondary/20",
    final: "bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800",
    notice: "bg-muted text-muted-foreground border-border",
    pairwise: "bg-amber-50 text-amber-700 border-amber-100 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800",
    round_started: "bg-stone-50 text-stone-600 border-stone-200",
    error: "bg-red-50 text-red-700 border-red-100 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800",
    debate_failed: "bg-red-50 text-red-700 border-red-100 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800",
  };
  return badges[type] ?? badges.notice;
};

const formatTimestamp = (value?: string) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

/** Build a stable React key for a debate event. */
function stableEventKey(event: DebateEvent, index: number): string {
  const at = "at" in event ? (event.at ?? "") : "";
  if (event.type === "score") return `score-${event.judge}-${event.persona}-${at}`;
  if (event.type === "message") return `msg-${(event as any).actor ?? ""}-${at}-${index}`;
  if (event.type === "seat_message") return `seat-${(event as any).seat_id ?? ""}-${at}-${index}`;
  return `${event.type}-${at}-${index}`;
}

/** Resolve the role for an event — seat_message maps to "agent". */
function resolveRole(event: DebateEvent): Role | undefined {
  if (event.type === "pairwise") return "judge";
  if (event.type === "score") return "judge";
  if (event.type === "final") return "synthesizer";
  if (event.type === "seat_message") return "agent";
  return (event as any).role as Role | undefined;
}

export default function DebateView({ events, className = "", embedded = false }: DebateViewProps) {
  const { t } = useI18n();

  return (
    <section
      className={embedded ? `px-0 ${className}` : `rounded-3xl border border-border bg-card p-6 ${className}`}
      aria-labelledby={embedded ? undefined : "debate-title"}
    >
      <div className="space-y-6">
        {!embedded && (
          <div className="text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-accent-secondary/20 bg-accent-secondary/5 px-4 py-1 text-xs font-semibold uppercase tracking-wide text-accent-secondary">
              <MessageSquare className="h-4 w-4" aria-hidden="true" />
              {t("debate.transcript.title")}
            </div>
            <h2 id="debate-title" className="mt-3 text-2xl font-semibold text-foreground">
              {t("debate.transcript.currentDebate")}
            </h2>
          </div>
        )}

        {/* Role legend */}
        <div className="rounded-2xl border border-border bg-secondary/50 p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("debate.transcript.roleLegend")}
          </h3>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
            <LegendDot color={ROLE_COLORS.agent.dot} label={t("debate.transcript.role.agent")} />
            <LegendDot color={ROLE_COLORS.critic.dot} label={t("debate.transcript.role.critic")} />
            <LegendDot color={ROLE_COLORS.judge.dot} label={t("debate.transcript.role.judge")} />
            <LegendDot color={ROLE_COLORS.synthesizer.dot} label={t("debate.transcript.role.synthesizer")} />
          </div>
        </div>

        {/* Event feed */}
        <div
          className="space-y-4"
          role="feed"
          aria-live="polite"
          aria-label="Debate transcript"
        >
          {events.length === 0 ? (
            <Card className="border border-border bg-secondary/50 p-8 text-center">
              <p className="text-sm text-muted-foreground">{t("debate.transcript.noEvents")}</p>
            </Card>
          ) : (
            events.map((event, index) => {
              const role = resolveRole(event);
              const { border, dot } = getRoleColors(role);
              const providerLabel = formatModelLabel(
                (event as any).provider ?? (event as any).model
              );

              // Actor / speaker label
              let actorNode: React.ReactNode = null;
              if (event.type === "message" && event.actor) {
                actorNode = (
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${dot}`} aria-hidden="true" />
                    <div>
                      <h4 className="text-sm font-semibold text-foreground">{event.actor}</h4>
                      {providerLabel && (
                        <p className="text-[0.68rem] text-muted-foreground">{providerLabel}</p>
                      )}
                    </div>
                  </div>
                );
              } else if (event.type === "seat_message" && event.seat_name) {
                actorNode = (
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${dot}`} aria-hidden="true" />
                    <div>
                      <h4 className="text-sm font-semibold text-foreground">{event.seat_name}</h4>
                      {providerLabel && (
                        <p className="text-[0.68rem] text-muted-foreground">{providerLabel}</p>
                      )}
                    </div>
                  </div>
                );
              } else if (event.type === "score" && "judge" in event) {
                actorNode = (
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${dot}`} aria-hidden="true" />
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <span className="font-semibold text-foreground">{event.judge}</span>
                      <span aria-hidden="true" className="text-muted-foreground/40">→</span>
                      <span className="text-muted-foreground">{event.persona}</span>
                    </div>
                  </div>
                );
              }

              return (
                <Card
                  key={stableEventKey(event, index)}
                  className={`border border-border bg-card p-5 shadow-sm transition hover:shadow-lg ${border} border-l-4`}
                  role="article"
                >
                  <div className="flex items-start justify-between mb-3 flex-wrap gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      {actorNode}

                      {/* Friendly event type badge */}
                      <Badge className={`${getTypeBadge(event.type)} border text-xs`}>
                        {formatEventType(event.type)}
                      </Badge>

                      {/* Round label */}
                      {"round" in event && event.round !== undefined && (
                        <span className="text-xs text-muted-foreground/60">
                          {t("debate.transcript.round")} {event.round}
                        </span>
                      )}
                    </div>

                    {formatTimestamp(event.at) && (
                      <time className="text-xs text-muted-foreground/60" dateTime={event.at}>
                        {formatTimestamp(event.at)}
                      </time>
                    )}
                  </div>

                  {/* Body text */}
                  {"text" in event && event.text && (
                    <p className="mb-3 text-sm leading-relaxed text-foreground/80">{event.text}</p>
                  )}
                  {event.type === "seat_message" && event.content && (
                    <p className="mb-3 text-sm leading-relaxed text-foreground/80">{event.content}</p>
                  )}

                  {/* Score detail box */}
                  {event.type === "score" && (
                    <div className="mt-3 space-y-2 rounded-lg border border-accent-secondary/20 bg-accent-secondary/5 p-3 text-xs text-foreground/80">
                      <div className="flex items-center justify-between text-sm font-semibold text-foreground">
                        <span>{t("debate.transcript.judgeLabel")} {event.judge}</span>
                        <span className="text-accent-secondary">{event.score.toFixed(2)}</span>
                      </div>
                      <div className="text-muted-foreground">
                        {t("debate.transcript.target")}: <span className="font-medium text-foreground">{event.persona}</span>
                      </div>
                      {event.rationale && (
                        <p className="leading-relaxed text-muted-foreground">{event.rationale}</p>
                      )}
                    </div>
                  )}
                </Card>
              );
            })
          )}
        </div>
      </div>
    </section>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`h-3 w-3 rounded-full ${color}`} aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
