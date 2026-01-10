import Link from "next/link";
import { getModelLeaderboard } from "@/lib/api";
import RosettaChamberLogo from "@/components/branding/RosettaChamberLogo";
import { getServerTranslations } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

export default async function ModelsPage() {
  const { t } = await getServerTranslations();
  const models = await getModelLeaderboard().catch(() => []);
  if (!models || models.length === 0) {
    return (
      <main id="main" className="space-y-6 p-6">
        <div className="flex items-center gap-3">
          <RosettaChamberLogo size={36} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">{t("models.kicker")}</p>
            <h1 className="text-3xl font-semibold text-slate-900 dark:text-white">{t("models.title")}</h1>
          </div>
        </div>
        <div className="rounded-3xl border border-dashed border-slate-200 bg-white/80 p-6 text-center shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <p className="text-base font-semibold text-slate-900 dark:text-white">{t("models.empty.title")}</p>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{t("models.empty.description")}</p>
          <div className="mt-4">
            <Link
              href="/"
              className="inline-flex items-center rounded-lg border border-amber-200 bg-amber-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-amber-500"
            >
              {t("models.empty.cta")}
            </Link>
          </div>
        </div>
      </main>
    );
  }
  return (
    <main id="main" className="space-y-6 p-6">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <RosettaChamberLogo size={36} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">{t("models.kicker")}</p>
            <h1 className="text-3xl font-semibold text-slate-900 dark:text-white">{t("models.title")}</h1>
          </div>
        </div>
        <p className="max-w-3xl text-sm text-slate-600 dark:text-slate-300">{t("models.description")}</p>
      </header>

      <div className="overflow-hidden rounded-2xl border border-amber-100 bg-amber-50/70 shadow-sm dark:border-slate-600 dark:bg-slate-800/50">
        <div className="grid grid-cols-4 gap-3 border-b border-amber-100 bg-amber-100/60 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-amber-800 dark:border-slate-600 dark:bg-slate-700 dark:text-amber-300">
          <span>{t("models.table.model")}</span>
          <span>{t("models.table.winRate")}</span>
          <span>{t("models.table.total")}</span>
          <span>{t("models.table.avgScore")}</span>
        </div>
        <div className="divide-y divide-amber-100 bg-white dark:divide-slate-600 dark:bg-slate-800">
          {models.map((item: any) => (
            <Link
              key={item.model}
              href={`/models/${encodeURIComponent(item.model)}`}
              className="grid grid-cols-4 items-center gap-3 px-4 py-3 text-sm transition-all duration-200 hover:-translate-y-[1px] hover:bg-amber-50 hover:shadow-sm dark:hover:bg-slate-700"
            >
              <span className="font-semibold text-slate-900 dark:text-white">{item.model}</span>
              <span className="text-amber-800 dark:text-amber-300">{(item.win_rate * 100).toFixed(1)}%</span>
              <span className="text-slate-700 dark:text-slate-300">{item.total_debates}</span>
              <span className="font-mono text-slate-800 dark:text-slate-200">
                {typeof item.avg_champion_score === "number" ? item.avg_champion_score.toFixed(2) : "—"}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}

