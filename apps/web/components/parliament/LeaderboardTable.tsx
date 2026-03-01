"use client";

import CIPill from "@/components/parliament/CIPill";
import type { LeaderboardEntry } from "@/lib/api";
import { useI18n } from "@/lib/i18n/client";

interface LeaderboardTableProps {
  items: LeaderboardEntry[];
}

export default function LeaderboardTable({ items }: LeaderboardTableProps) {
  const { t } = useI18n();
  return (
    <div className="overflow-x-auto rounded-3xl border border-border bg-card shadow-sm">
      <table className="min-w-full divide-y divide-border text-sm">
        <thead className="bg-secondary text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-4 py-3">{t("leaderboard.table.persona")}</th>
            <th className="px-4 py-3">{t("leaderboard.table.category")}</th>
            <th className="px-4 py-3 text-right">{t("leaderboard.table.elo")}</th>
            <th className="px-4 py-3 text-right">{t("leaderboard.table.winRate")}</th>
            <th className="px-4 py-3 text-right">{t("leaderboard.table.matches")}</th>
            <th className="px-4 py-3 text-right">{t("leaderboard.table.updated")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border text-foreground">
          {items.map((entry) => (
            <tr key={`${entry.persona}-${entry.category ?? "all"}`} className="transition-colors hover:bg-secondary/50 focus-within:bg-secondary/50">
              <td className="px-4 py-3 font-semibold text-foreground">
                <span className="flex items-center gap-2">
                  {entry.persona}
                  {entry.badge ? (
                    <span className="rounded-full bg-accent-secondary/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-accent-secondary">
                      {entry.badge}
                    </span>
                  ) : null}
                </span>
              </td>
              <td className="px-4 py-3 text-muted-foreground">{entry.category ?? t("leaderboard.filters.categoryAll")}</td>
              <td className="px-4 py-3 text-right font-mono text-base">{entry.elo.toFixed(1)}</td>
              <td className="px-4 py-3 text-right">
                <CIPill winRate={entry.win_rate} low={entry.ci.low} high={entry.ci.high} className="justify-end" />
              </td>
              <td className="px-4 py-3 text-right font-mono">{entry.n_matches}</td>
              <td className="px-4 py-3 text-right text-xs text-muted-foreground">
                {entry.last_updated ? new Date(entry.last_updated).toLocaleString() : "—"}
              </td>
            </tr>
          ))}
          {items.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-4 py-10 text-center text-sm text-muted-foreground">
                {t("leaderboard.table.empty")}
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
