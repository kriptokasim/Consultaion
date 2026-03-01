"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MessageSquare } from "lucide-react";
import { useI18n } from "@/lib/i18n/client";
import type { DebateEvent, Role } from "./types";

export interface DebateViewProps {
  events: DebateEvent[];
  className?: string;
}

const getRoleColor = (role?: Role) => {
  const colors = {
    agent: "border-l-blue-300 dark:border-l-blue-500",
    critic: "border-l-purple-300 dark:border-l-purple-500",
    judge: "border-l-accent-secondary",
    synthesizer: "border-l-emerald-300 dark:border-l-emerald-500",
  };
  return `border-l-4 ${role ? colors[role] ?? "border-l-border" : "border-l-border"}`;
};

const getTypeBadge = (type: string) => {
  const badges = {
    message: "bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800",
    score: "bg-accent-secondary/10 text-accent-secondary border-accent-secondary/20",
    final: "bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800",
    notice: "bg-muted text-muted-foreground border-border",
  };
  return badges[type as keyof typeof badges] || badges.notice;
};

const formatTimestamp = (value?: string) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

export default function DebateView({ events, className = "" }: DebateViewProps) {
  const { t } = useI18n();

  return (
    <section
      className={`rounded-3xl border border-border bg-card p-6 ${className}`}
      aria-labelledby="debate-title"
    >
      <div className="space-y-6">
        <div className="text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-accent-secondary/20 bg-accent-secondary/5 px-4 py-1 text-xs font-semibold uppercase tracking-wide text-accent-secondary">
            <MessageSquare className="h-4 w-4" aria-hidden="true" />
            {t("debate.transcript.title")}
          </div>
          <h2 id="debate-title" className="mt-3 text-2xl font-semibold text-foreground">
            {t("debate.transcript.currentDebate")}
          </h2>
        </div>

        <div className="rounded-2xl border border-border bg-secondary/50 p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("debate.transcript.roleLegend")}
          </h3>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
            <LegendDot color="bg-blue-500" label={t("debate.transcript.role.agent")} />
            <LegendDot color="bg-purple-500" label={t("debate.transcript.role.critic")} />
            <LegendDot color="bg-amber-500" label={t("debate.transcript.role.judge")} />
            <LegendDot color="bg-emerald-500" label={t("debate.transcript.role.synthesizer")} />
          </div>
        </div>

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
            events.map((event, index) => (
              <Card
                key={index}
                className={`border border-border bg-card p-5 shadow-sm transition hover:shadow-lg ${getRoleColor(
                  event.type === "pairwise" ? "judge" : (event as any).role,
                )}`}
                role="article"
              >
                <div className="flex items-start justify-between mb-3 flex-wrap gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    {event.type === "message" && event.actor && (
                      <h4 className="text-sm font-semibold text-foreground">{event.actor}</h4>
                    )}

                    {event.type === "score" && "judge" in event && (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span className="font-semibold text-foreground">{event.judge}</span>
                        <span aria-hidden="true" className="text-muted-foreground/40">→</span>
                        <span className="text-muted-foreground">{event.persona}</span>
                      </div>
                    )}

                    <Badge className={`${getTypeBadge(event.type)} border text-xs`}>
                      {event.type}
                    </Badge>

                    {"round" in event && event.round !== undefined && (
                      <span className="text-xs text-muted-foreground/60">{t("debate.transcript.round")} {event.round}</span>
                    )}
                  </div>

                  {formatTimestamp(event.at) && (
                    <time className="text-xs text-muted-foreground/60" dateTime={event.at}>
                      {formatTimestamp(event.at)}
                    </time>
                  )}
                </div>

                {"text" in event && event.text && (
                  <p className="mb-3 text-sm leading-relaxed text-foreground/80">{event.text}</p>
                )}

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
            ))
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
