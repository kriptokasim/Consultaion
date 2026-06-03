"use client";

import Link from "next/link";
import { Play } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DebateListSkeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyStateModern } from "@/components/ui/empty-state-modern";
import type { DebateSummary } from "@/app/(app)/dashboard/types";
import { useI18n } from "@/lib/i18n/client";

type DashboardRunsHistoryProps = {
  debates: DebateSummary[];
  debatesLoading: boolean;
  onNewRun: () => void;
};

function formatTimestamp(ts?: string | null) {
  if (!ts) return "Just now";
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "Just now";
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function statusTone(status?: string | null) {
  switch ((status || "").toLowerCase()) {
    case "running":
      return "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/50 dark:text-amber-200 dark:border-amber-700";
    case "completed":
    case "done":
      return "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/50 dark:text-emerald-200 dark:border-emerald-700";
    case "queued":
    default:
      return "bg-secondary text-foreground border-border";
  }
}

export function DashboardRunsHistory({ debates, debatesLoading, onNewRun }: DashboardRunsHistoryProps) {
  const { t } = useI18n();

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-accent-secondary">{t("dashboard.section.recent.kicker")}</p>
          <h2 className="heading-serif text-2xl font-semibold text-foreground">{t("dashboard.section.recent.title")}</h2>
        </div>
        <Link href="/runs" className="text-sm font-semibold text-primary hover:text-primary/80">
          {t("dashboard.section.recent.link")}
        </Link>
      </div>
      {debatesLoading ? (
        <DebateListSkeleton />
      ) : debates.length === 0 ? (
        <EmptyStateModern
          icon={<Play className="h-6 w-6" />}
          title={t("dashboard.empty.title")}
          description={t("dashboard.empty.description")}
          action={{
            label: t("dashboard.empty.cta"),
            onClick: onNewRun
          }}
          className="bg-card shadow-smooth"
        />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-smooth">
          <div className="divide-y divide-border">
            {debates.map((debate) => {
              const replayAvailable = (debate.status || "").toLowerCase() === "completed" || (debate.status || "").toLowerCase() === "failed";
              return (
                <div
                  key={debate.id}
                  className="flex items-center gap-4 px-5 py-4 transition hover:bg-secondary/50"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary shadow-inner">
                    <Play className="h-5 w-5" />
                  </div>
                  <Link href={`/runs/${debate.id}`} className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-foreground line-clamp-1 hover:text-primary transition-colors">{debate.prompt || t("dashboard.prompt.untitled")}</p>
                    <p className="text-xs text-muted-foreground">{t("dashboard.time.createdPrefix")} {formatTimestamp(debate.created_at)}</p>
                  </Link>
                  <div className="flex items-center gap-2">
                    {replayAvailable ? (
                      <Link href={`/runs/${debate.id}/replay`} className="text-xs font-semibold text-primary underline-offset-4 hover:underline">
                        {t("dashboard.recentDebates.replay")}
                      </Link>
                    ) : null}
                    <Badge className={`border ${statusTone(debate.status)}`}>{debate.status ?? "queued"}</Badge>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </section>
  );
}
