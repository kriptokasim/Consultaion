import Brand from "@/components/parliament/Brand";
import { getServerTranslations } from "@/lib/i18n/server";

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
      <header className="rounded-3xl border border-stone-200 bg-gradient-to-br from-white via-amber-50 to-stone-50 p-6 shadow">
        <div className="flex items-center gap-3">
          <Brand variant="mark" height={28} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">{t("methodology.kicker")}</p>
            <h1 className="text-3xl font-semibold text-stone-900">{t("methodology.title")}</h1>
          </div>
        </div>
        <p className="mt-3 max-w-3xl text-sm text-stone-600">{t("methodology.description")}</p>
      </header>
      <section className="space-y-6 rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
        {sections.map((section) => (
          <article key={section.title}>
            <h2 className="text-xl font-semibold text-stone-900">{section.title}</h2>
            <p className="mt-2 text-sm text-stone-600" dangerouslySetInnerHTML={{ __html: section.body }} />
          </article>
        ))}
      </section>
      <section className="mt-10 rounded-3xl border border-amber-100/70 bg-white p-6 shadow-[0_16px_36px_rgba(112,73,28,0.12)] dark:border-amber-900/50 dark:bg-stone-900/80">
        <h2 className="text-xl font-semibold text-stone-900 dark:text-amber-50">{t("methodology.section.brand.title")}</h2>
        <p className="mt-2 text-sm text-stone-600 dark:text-stone-200">{t("methodology.section.brand.body")}</p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <BrandCell label={t("methodology.section.brand.markStone") } tone="stone" />
          <BrandCell label={t("methodology.section.brand.markAmber") } tone="amber" />
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
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-amber-100/80 bg-white p-4 text-center shadow-sm dark:border-amber-900/40 dark:bg-stone-900">
      <Brand variant={variant} tone={tone} height={variant === "mark" ? 48 : 32} />
      <p className="text-xs font-semibold uppercase tracking-wide text-stone-600 dark:text-amber-100">{label}</p>
    </div>
  );
}
