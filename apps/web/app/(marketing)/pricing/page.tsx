import { getBillingPlans, type BillingPlanSummary } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getServerTranslations } from "@/lib/i18n/server";

export const revalidate = 3600;

async function fetchPlans(): Promise<BillingPlanSummary[]> {
  try {
    return await getBillingPlans();
  } catch {
    return [];
  }
}

export default async function PricingPage() {
  const { t } = await getServerTranslations();
  const plans = await fetchPlans();
  return (
    <main className="mx-auto max-w-5xl space-y-8 px-6 py-16">
      <div className="text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-700 dark:text-amber-400">{t("pricing.kicker")}</p>
        <h1 className="heading-serif text-4xl text-slate-900 dark:text-white">{t("pricing.title")}</h1>
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{t("pricing.description")}</p>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        {plans.map((plan) => (
          <Card key={plan.slug} className="border-amber-200 bg-white/90 p-6 shadow-[0_20px_50px_rgba(112,73,28,0.08)] dark:border-slate-600 dark:bg-slate-800">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-amber-600 dark:text-amber-400">{plan.is_default_free ? t("pricing.plan.starter") : t("pricing.plan.premium")}</p>
                <h2 className="heading-serif text-2xl text-slate-900 dark:text-white">{plan.name}</h2>
              </div>
              <div className="text-right text-3xl font-semibold text-slate-900 dark:text-white">
                {plan.price_monthly ? `$${plan.price_monthly.toFixed(2)}` : t("pricing.plan.free")}
                <span className="text-xs font-normal text-slate-500 dark:text-slate-400">{t("pricing.plan.perMonth")}</span>
              </div>
            </div>
            <ul className="mt-4 space-y-2 text-sm text-slate-600 dark:text-slate-300">
              <li>• {plan.limits?.max_debates_per_month ?? "?"} {t("pricing.plan.debates")}</li>
              <li>• {plan.limits?.max_models_per_debate ?? 3} {t("pricing.plan.models")}</li>
              <li>
                • {plan.limits?.exports_enabled ? t("pricing.plan.exportsEnabled") : t("pricing.plan.exportsDisabled")}
              </li>
            </ul>
            <Button asChild className="mt-6 w-full bg-amber-600 text-white hover:bg-amber-700">
              <a href={`/settings/billing?plan=${plan.slug}`}>{t("pricing.plan.cta")} {plan.name}</a>
            </Button>
          </Card>
        ))}
      </div>
    </main>
  );
}

