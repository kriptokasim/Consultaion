import Link from "next/link";
import { getModelDetail } from "@/lib/api";
import Brand from "@/components/parliament/Brand";
import { getServerTranslations } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

export default async function ModelDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = await getServerTranslations();
  const { id } = await params;
  const data = await getModelDetail(id).catch(() => null);

  if (!data) {
    return (
      <main className="p-6">
        <p className="text-sm text-slate-600 dark:text-slate-300">{t("modelDetail.error")}</p>
      </main>
    );
  }

  return (
    <main id="main" className="space-y-6 p-6">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <Brand height={32} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">{t("modelDetail.kicker")}</p>
            <h1 className="text-3xl font-semibold text-slate-900 dark:text-white">{data.model}</h1>
            <p className="text-sm text-slate-600 dark:text-slate-300">{t("modelDetail.description")}</p>
          </div>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <StatCard
          label={t("modelDetail.stats.winRate")}
          value={`${(data.win_rate * 100).toFixed(1)}%`}
          icon={<Brand height={16} className="text-amber-700" />}
        />
        <StatCard label={t("modelDetail.stats.total")} value={data.total_debates} />
        <StatCard
          label={t("modelDetail.stats.avgScore")}
          value={typeof data.avg_score_overall === "number" ? data.avg_score_overall.toFixed(2) : "—"}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{t("modelDetail.recentTitle")}</h2>
        <div className="divide-y divide-amber-100 dark:divide-slate-700 rounded-2xl border border-amber-100 dark:border-slate-800 bg-white dark:bg-slate-900/50 shadow-sm">
          {Array.isArray(data.recent_debates) && data.recent_debates.length ? (
            data.recent_debates.map((debate: any) => (
              <Link
                key={debate.debate_id}
                href={`/runs/${debate.debate_id}`}
                className="flex flex-col gap-1 px-4 py-3 text-sm transition hover:bg-amber-50 dark:hover:bg-slate-800"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-900 dark:text-white">{debate.prompt}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${debate.was_champion ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300" : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                      }`}
                  >
                    {debate.was_champion ? t("modelDetail.recent.champion") : t("modelDetail.recent.participant")}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
                  <span>
                    {t("modelDetail.recent.championLabel")}
                    {debate.champion ?? t("modelDetail.recent.championUnknown")}
                  </span>
                  {typeof debate.champion_score === "number" ? <span>Score {debate.champion_score.toFixed(2)}</span> : null}
                  {debate.created_at ? <span> • {new Date(debate.created_at).toLocaleString()}</span> : null}
                </div>
              </Link>
            ))
          ) : (
            <p className="px-4 py-3 text-sm text-slate-600 dark:text-slate-300">{t("modelDetail.emptyRecent")}</p>
          )}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{t("modelDetail.samplesTitle")}</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {Array.isArray(data.champion_samples) && data.champion_samples.length ? (
            data.champion_samples.map((sample: any) => (
              <article key={sample.debate_id} className="flex h-full flex-col rounded-2xl border border-amber-100 bg-amber-50/60 dark:border-slate-800 dark:bg-slate-900/50 p-4 shadow-sm">
                <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">
                  <Brand height={16} />
                  {t("modelDetail.samples.prompt")}
                </p>
                <p className="mb-2 text-sm font-semibold text-slate-900 dark:text-white">{sample.prompt}</p>
                {sample.excerpt ? (
                  <p className="flex-1 text-sm text-slate-700 dark:text-slate-300">{sample.excerpt}</p>
                ) : (
                  <p className="flex-1 text-sm text-slate-600 dark:text-slate-400">{t("modelDetail.samples.noExcerpt")}</p>
                )}
                <Link
                  href={`/runs/${sample.debate_id}`}
                  className="mt-3 inline-flex items-center rounded-lg border border-amber-200 bg-white dark:border-slate-700 dark:bg-slate-800 px-3 py-2 text-xs font-semibold text-amber-800 dark:text-amber-300 transition hover:border-amber-400"
                >
                  {t("modelDetail.samples.cta")} →
                </Link>
              </article>
            ))
          ) : (
            <p className="text-sm text-slate-600 dark:text-slate-400">{t("modelDetail.emptySamples")}</p>
          )}
        </div>
      </section>
    </main>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string | number; icon?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-amber-100 bg-gradient-to-br from-amber-50 via-white to-stone-50 dark:border-slate-800 dark:from-slate-900 dark:via-slate-900/80 dark:to-slate-950 p-4 shadow-sm">
      <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">
        {icon ? icon : null}
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold text-slate-900 dark:text-white">{value}</p>
    </div>
  );
}
