"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n/client";
import type { LeaderboardEntry } from "@/lib/api";
import type { HallOfFameEntry, ModelStatsSummary } from "@/lib/api/types";

export interface ModelRegistrySurfaceProps {
  modelStats: ModelStatsSummary[];
  leaderboard: LeaderboardEntry[];
  hallOfFame: HallOfFameEntry[];
}

type TabId = "models" | "leaderboard" | "hall-of-fame";
const TAB_IDS: TabId[] = ["models", "leaderboard", "hall-of-fame"];

function readHashTab(): TabId {
  if (typeof window === "undefined") return "models";
  const hash = window.location.hash.replace("#", "");
  return (TAB_IDS as string[]).includes(hash) ? (hash as TabId) : "models";
}

/**
 * PS07: Models, Leaderboard and Hall of Fame consolidated onto one page,
 * switched by hash (#models / #leaderboard / #hall-of-fame) instead of
 * three separate routes/scroll state, per DESIGN-SPEC "Models/Leaderboard/
 * Hall of Fame become one model registry" and NEW_UX_AGENT_TASK's "hash
 * navigation instead of scroll-only state". All three datasets are the
 * same real, backend-derived data the previous three pages already used
 * (GET /stats/models, /leaderboard, /stats/hall-of-fame) — nothing invented.
 */
export function ModelRegistrySurface({ modelStats, leaderboard, hallOfFame }: ModelRegistrySurfaceProps) {
  const { t } = useI18n();
  const [tab, setTab] = useState<TabId>("models");

  useEffect(() => {
    setTab(readHashTab());
    const onHashChange = () => setTab(readHashTab());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const selectTab = (next: TabId) => {
    setTab(next);
    window.location.hash = next;
  };

  return (
    <main id="main" className="new-ux-marketing__shell new-ux-marketing__section" style={{ borderTop: 0 }}>
      <p className="new-ux-marketing__kicker">{t("marketing.registry.title")}</p>
      <h1 className="new-ux-marketing__section-title">{t("marketing.registry.title")}</h1>
      <p className="new-ux-marketing__lede">{t("marketing.registry.lede")}</p>

      <div className="new-ux-marketing__tabs" role="tablist" aria-label={t("marketing.registry.title")}>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "models"}
          aria-current={tab === "models" ? "page" : undefined}
          className="new-ux-marketing__tab"
          onClick={() => selectTab("models")}
        >
          {t("marketing.registry.tabs.models")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "leaderboard"}
          aria-current={tab === "leaderboard" ? "page" : undefined}
          className="new-ux-marketing__tab"
          onClick={() => selectTab("leaderboard")}
        >
          {t("marketing.registry.tabs.leaderboard")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "hall-of-fame"}
          aria-current={tab === "hall-of-fame" ? "page" : undefined}
          className="new-ux-marketing__tab"
          onClick={() => selectTab("hall-of-fame")}
        >
          {t("marketing.registry.tabs.hallOfFame")}
        </button>
      </div>

      {tab === "models" && <ModelsPanel stats={modelStats} />}
      {tab === "leaderboard" && <LeaderboardPanel entries={leaderboard} />}
      {tab === "hall-of-fame" && <HallOfFamePanel entries={hallOfFame} />}

      <p className="new-ux-marketing__hero-hint" style={{ marginTop: 24 }}>
        {t("marketing.registry.caveat")}
      </p>
    </main>
  );
}

function ModelsPanel({ stats }: { stats: ModelStatsSummary[] }) {
  const { t } = useI18n();
  if (stats.length === 0) {
    return <p className="new-ux-marketing__empty">{t("marketing.registry.models.empty")}</p>;
  }
  return (
    <table className="new-ux-marketing__table">
      <thead>
        <tr>
          <th>{t("marketing.registry.models.table.model")}</th>
          <th>{t("marketing.registry.models.table.winRate")}</th>
          <th>{t("marketing.registry.models.table.total")}</th>
          <th>{t("marketing.registry.models.table.avgScore")}</th>
        </tr>
      </thead>
      <tbody>
        {stats.map((item) => (
          <tr key={item.model}>
            <td>
              <Link href={`/models/${encodeURIComponent(item.model)}`}>{item.model}</Link>
            </td>
            <td>{(item.win_rate * 100).toFixed(1)}%</td>
            <td>{item.total_debates}</td>
            <td>{typeof item.avg_champion_score === "number" ? item.avg_champion_score.toFixed(2) : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function LeaderboardPanel({ entries }: { entries: LeaderboardEntry[] }) {
  const { t } = useI18n();
  if (entries.length === 0) {
    return <p className="new-ux-marketing__empty">{t("marketing.registry.leaderboard.empty")}</p>;
  }
  return (
    <table className="new-ux-marketing__table">
      <thead>
        <tr>
          <th>{t("marketing.registry.models.table.model")}</th>
          <th>Elo</th>
          <th>{t("marketing.registry.models.table.total")}</th>
          <th>{t("leaderboard.filters.category")}</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.persona}>
            <td>{entry.persona}</td>
            <td>{Math.round(entry.elo)}</td>
            <td>{entry.n_matches}</td>
            <td>{entry.category || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function HallOfFamePanel({ entries }: { entries: HallOfFameEntry[] }) {
  const { t } = useI18n();
  if (entries.length === 0) {
    return <p className="new-ux-marketing__empty">{t("marketing.registry.hallOfFame.empty")}</p>;
  }
  return (
    <div style={{ marginTop: 20, display: "grid", gap: 1, background: "var(--rule)", border: "1px solid var(--rule)" }}>
      {entries.map((entry) => (
        <article key={entry.id} className="new-ux-marketing__plan">
          <span className="new-ux-marketing__plan-name">{t("marketing.registry.hallOfFame.championLabel")}</span>
          <p style={{ margin: 0, fontWeight: 600 }}>{entry.champion || "—"}</p>
          <p style={{ margin: "4px 0 0", color: "var(--ink-soft)", fontSize: "var(--text-utility)" }}>{entry.prompt}</p>
          <p style={{ margin: "8px 0 0", fontSize: "var(--text-utility)", color: "var(--ink-soft)" }}>
            {entry.champion_excerpt || t("marketing.registry.hallOfFame.noExcerpt")}
          </p>
          <div className="new-ux-marketing__plan-cta">
            <Link href={`/runs/${entry.id}`} className="new-ux-marketing__secondary">
              {t("workspace.report.openFull")}
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}
