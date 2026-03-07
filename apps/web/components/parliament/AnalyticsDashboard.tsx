"use client";

import { Activity, ArrowUpRight, BarChart3, Clock, Hash, TrendingUp } from "lucide-react";
import { useI18n } from "@/lib/i18n/client";
import { formatStatus } from "@/lib/ui/formatters";

export interface AnalyticsActivityItem {
  id: string;
  title: string;
  timestamp: string;
  status: string;
}

export interface AnalyticsWinRate {
  persona: string;
  wins: number;
  total: number;
}

export interface AnalyticsData {
  totals: {
    debates: number;
    completed: number;
    completionRate: number;
    avgDurationMinutes: number;
  };
  winRates: AnalyticsWinRate[];
  scoreDistribution: { label: string; count: number }[];
  activity: AnalyticsActivityItem[];
}

interface AnalyticsDashboardProps {
  data: AnalyticsData;
}

/** Format a timestamp as a relative "N minutes ago" string. */
function relativeTime(ts: string): string {
  const diffMs = Date.now() - new Date(ts).getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return new Date(ts).toLocaleDateString();
}

export default function AnalyticsDashboard({ data }: AnalyticsDashboardProps) {
  const { t } = useI18n();

  // Normalise score distribution bar widths against the actual max count
  const maxScoreCount = Math.max(1, ...data.scoreDistribution.map((b) => b.count));
  // Normalise win-rate bar widths
  const maxWinTotal = Math.max(1, ...data.winRates.map((r) => r.total));

  return (
    <section className="space-y-6">
      <header className="rounded-3xl border border-stone-200 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-6 shadow-[0_20px_45px_rgba(120,113,108,0.12)] dark:border-border dark:from-stone-900 dark:via-card dark:to-stone-900">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
          {t("analytics.header.kicker")}
        </p>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-3xl font-semibold text-stone-900 dark:text-foreground">
            {t("analytics.header.title")}
          </h1>
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-white px-4 py-2 text-xs font-semibold uppercase tracking-wide text-amber-700 dark:border-amber-800 dark:bg-card dark:text-amber-400">
            <BarChart3 className="h-4 w-4" />
            {t("analytics.header.badge")}
          </span>
        </div>
        <p className="mt-3 text-sm text-stone-600 dark:text-muted-foreground">
          {t("analytics.header.description")}
        </p>
      </header>

      {/* Stat cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard
          label={t("analytics.stats.debates")}
          value={data.totals.debates}
          icon={<Hash className="h-4 w-4 text-amber-500" />}
        />
        <StatCard
          label={t("analytics.stats.completionRate")}
          value={`${Math.round(data.totals.completionRate * 100)}%`}
          icon={<TrendingUp className="h-4 w-4 text-amber-500" />}
        />
        <StatCard
          label={t("analytics.stats.avgDuration")}
          value={`${data.totals.avgDurationMinutes.toFixed(1)}m`}
          icon={<Clock className="h-4 w-4 text-amber-500" />}
        />
        <StatCard
          label={t("analytics.stats.completed")}
          value={data.totals.completed}
          icon={<ArrowUpRight className="h-4 w-4 text-amber-500" />}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        {/* Win rates */}
        <div className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm dark:border-border dark:bg-card">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-muted-foreground">
              {t("analytics.sections.winRates.kicker")}
            </p>
            <h3 className="text-xl font-semibold text-stone-900 dark:text-foreground">
              {t("analytics.sections.winRates.title")}
            </h3>
          </div>
          <div className="mt-6 space-y-4">
            {data.winRates.length === 0 ? (
              <EmptyState message={t("analytics.empty.winRates")} />
            ) : (
              data.winRates.map((rate) => {
                const pct = Math.round((rate.wins / Math.max(1, rate.total)) * 100);
                return (
                  <div key={rate.persona} className="space-y-2 rounded-xl border border-stone-100 p-4 dark:border-border">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-semibold text-stone-800 dark:text-foreground">
                        {rate.persona}
                      </span>
                      <span className="text-stone-500 dark:text-muted-foreground">
                        {rate.wins}/{rate.total} {t("analytics.winSuffix")}
                      </span>
                    </div>
                    {/* Accessible meter bar */}
                    <div
                      className="h-2 rounded-full bg-stone-200 dark:bg-muted"
                      role="meter"
                      aria-label={`${rate.persona} win rate`}
                      aria-valuenow={pct}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-amber-500 to-amber-300 transition-all dark:from-amber-400 dark:to-amber-600"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Score distribution */}
        <div className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm dark:border-border dark:bg-card">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-muted-foreground">
              {t("analytics.sections.score.kicker")}
            </p>
            <h3 className="text-xl font-semibold text-stone-900 dark:text-foreground">
              {t("analytics.sections.score.title")}
            </h3>
          </div>
          <div className="mt-6 space-y-3">
            {data.scoreDistribution.length === 0 ? (
              <EmptyState message={t("analytics.empty.score")} />
            ) : (
              data.scoreDistribution.map((bucket) => {
                const pct = Math.round((bucket.count / maxScoreCount) * 100);
                return (
                  <div key={bucket.label} className="flex items-center gap-3">
                    <span className="w-16 text-xs font-semibold uppercase tracking-wide text-stone-400 dark:text-muted-foreground">
                      {bucket.label}
                    </span>
                    <div
                      className="h-2 flex-1 rounded-full bg-stone-100 dark:bg-muted"
                      role="meter"
                      aria-label={`Score bucket ${bucket.label}`}
                      aria-valuenow={pct}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      <div
                        className="h-full rounded-full bg-amber-400/80 transition-all dark:bg-amber-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="w-10 text-right text-sm font-medium text-stone-600 dark:text-muted-foreground">
                      {bucket.count}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Recent activity */}
      <div className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm dark:border-border dark:bg-card">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-muted-foreground">
          <Activity className="h-4 w-4 text-amber-500" />
          {t("analytics.sections.activity.kicker")}
        </div>
        <div className="mt-4 divide-y divide-stone-100 dark:divide-border">
          {data.activity.length === 0 ? (
            <EmptyState message={t("analytics.empty.activity")} />
          ) : (
            data.activity.map((item) => (
              <div
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm text-stone-700 dark:text-foreground/80"
              >
                <div>
                  <p className="font-semibold text-stone-900 dark:text-foreground">{item.title}</p>
                  {/* Friendly status label instead of raw string */}
                  <p className="text-xs text-stone-500 dark:text-muted-foreground">
                    {formatStatus(item.status)}
                  </p>
                </div>
                {/* Relative timestamp */}
                <time
                  className="text-xs font-semibold text-amber-700 dark:text-amber-400"
                  dateTime={item.timestamp}
                  title={new Date(item.timestamp).toLocaleString()}
                >
                  {relativeTime(item.timestamp)}
                </time>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white/80 p-4 shadow-inner dark:border-border dark:bg-card/80">
      <div className="flex items-center justify-between text-stone-500 dark:text-muted-foreground">
        <span className="text-xs font-semibold uppercase tracking-wide">{label}</span>
        {icon}
      </div>
      <p className="mt-4 text-2xl font-semibold text-stone-900 dark:text-foreground">{value}</p>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-stone-200 bg-stone-50/70 p-6 text-center text-sm text-stone-500 dark:border-border dark:bg-muted/30 dark:text-muted-foreground">
      {message}
    </div>
  );
}
