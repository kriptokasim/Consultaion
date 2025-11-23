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
    <div className="overflow-x-auto rounded-3xl border border-stone-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-stone-100 text-sm">
        <thead className="bg-stone-50 text-left text-xs font-semibold uppercase tracking-wide text-stone-500">
          <tr>
            <th className="px-4 py-3">{t("leaderboard.table.persona")}</th>
            <th className="px-4 py-3">{t("leaderboard.table.category")}</th>
            <th className="px-4 py-3 text-right">{t("leaderboard.table.elo")}</th>
            <th className="px-4 py-3 text-right">{t("leaderboard.table.winRate")}</th>
            <th className="px-4 py-3 text-right">{t("leaderboard.table.matches")}</th>
            <th className="px-4 py-3 text-right">{t("leaderboard.table.updated")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100 text-stone-800">
          {items.map((entry) => (
            <tr key={`${entry.persona}-${entry.category ?? "all"}`}>
              <td className="px-4 py-3 font-semibold text-stone-900">
                <span className="flex items-center gap-2">
                  {entry.persona}
                  {entry.badge ? (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-800">
                      {entry.badge}
                    </span>
                  ) : null}
                </span>
              </td>
              <td className="px-4 py-3 text-stone-600">{entry.category ?? t("leaderboard.filters.categoryAll")}</td>
              <td className="px-4 py-3 text-right font-mono text-base">{entry.elo.toFixed(1)}</td>
              <td className="px-4 py-3 text-right">
                <CIPill winRate={entry.win_rate} low={entry.ci.low} high={entry.ci.high} className="justify-end" />
              </td>
              <td className="px-4 py-3 text-right font-mono">{entry.n_matches}</td>
              <td className="px-4 py-3 text-right text-xs text-stone-500">
                {entry.last_updated ? new Date(entry.last_updated).toLocaleString() : "—"}
              </td>
            </tr>
          ))}
          {items.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-4 py-10 text-center text-sm text-stone-500">
                {t("leaderboard.table.empty")}
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
