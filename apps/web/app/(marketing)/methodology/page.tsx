import Brand from "@/components/parliament/Brand";
import { getServerTranslations } from "@/lib/i18n/server";
import type { Metadata } from 'next';
import { Layers, Scale, ShieldCheck } from "lucide-react";

export const metadata: Metadata = {
  title: 'Methodology & Rankings Science',
  description: 'Learn how Consultaion ranks AI models using pairwise Elo matching, Wilson intervals, and anti-gaming algorithms.',
};

export const dynamic = "force-dynamic";

export default async function MethodologyPage() {
  const { t } = await getServerTranslations();
  const sections = [
    { title: t("methodology.section.pairwise.title"), body: t("methodology.section.pairwise.body") },
    { title: t("methodology.section.elo.title"), body: t("methodology.section.elo.body") },
    { title: t("methodology.section.wilson.title"), body: t("methodology.section.wilson.body") },
    { title: t("methodology.section.cadence.title"), body: t("methodology.section.cadence.body") },
    { title: t("methodology.section.antigaming.title"), body: t("methodology.section.antigaming.body") },
  ];
  return (
    <main id="main" className="space-y-6 p-4">
      <header className="rounded-3xl border border-slate-200 bg-gradient-to-br from-white via-amber-50 to-slate-50 p-6 shadow dark:border-slate-600 dark:from-slate-800 dark:via-slate-800 dark:to-slate-900">
        <div className="flex items-center gap-3">
          <Brand variant="mark" height={28} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">{t("methodology.kicker")}</p>
            <h1 className="text-3xl font-semibold text-slate-900 dark:text-white">{t("methodology.title")}</h1>
          </div>
        </div>
        <p className="mt-3 max-w-3xl text-sm text-slate-600 dark:text-slate-300">{t("methodology.description")}</p>
      </header>

      {/* Executive Summary / Value Prop */}
      <section id="executive-summary-section" className="rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-50 to-indigo-50/30 p-6 shadow-sm dark:border-slate-850 dark:from-slate-900/50 dark:to-slate-900/10">
        <h2 className="text-xl font-semibold text-slate-950 dark:text-white">{t("methodology.executiveSummary.title")}</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{t("methodology.executiveSummary.subtitle")}</p>
        <div className="mt-6 grid gap-6 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-450">
              <Layers className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-sm font-semibold text-slate-900 dark:text-white">360° Risk Analysis</h3>
            <p className="mt-2 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              {t("methodology.executiveSummary.benefit1")}
            </p>
          </div>
          
          <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-450">
              <Scale className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-sm font-semibold text-slate-900 dark:text-white">Unbiased Decisions</h3>
            <p className="mt-2 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              {t("methodology.executiveSummary.benefit2")}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-450">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-sm font-semibold text-slate-900 dark:text-white">Defensible Outcomes</h3>
            <p className="mt-2 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              {t("methodology.executiveSummary.benefit3")}
            </p>
          </div>
        </div>
      </section>

      <section id="rankings-science-section" className="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
        {sections.map((section) => (
          <article key={section.title} className="border-b border-slate-100 last:border-0 pb-6 last:pb-0 dark:border-slate-700">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">{section.title}</h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300" dangerouslySetInnerHTML={{ __html: section.body }} />
          </article>
        ))}
      </section>

      <section id="enterprise-features-section" className="mt-10 rounded-3xl border border-amber-100/70 bg-white p-6 shadow-[0_16px_36px_#70491c1f] dark:border-slate-600 dark:bg-slate-800">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">{t("methodology.section.brand.title")}</h2>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{t("methodology.section.brand.body")}</p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <BrandCell label={t("methodology.section.brand.markStone")} tone="stone" />
          <BrandCell label={t("methodology.section.brand.markAmber")} tone="amber" />
          <BrandCell label={t("methodology.section.brand.wordmark")} tone="stone" variant="logotype" />
        </div>
      </section>
    </main>
  );
}


function BrandCell({
  label,
  tone,
  variant = "mark",
}: {
  label: string;
  tone: "stone" | "amber";
  variant?: "mark" | "logotype";
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-amber-100/80 bg-white p-4 text-center shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <Brand variant={variant} tone={tone} height={variant === "mark" ? 48 : 32} />
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">{label}</p>
    </div>
  );
}
