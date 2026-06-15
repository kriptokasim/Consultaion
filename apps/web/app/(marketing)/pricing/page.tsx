import { getBillingPlans, type BillingPlanSummary } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getServerTranslations } from "@/lib/i18n/server";
import type { Metadata } from 'next';
import Link from "next/link";

export const metadata: Metadata = {
  title: 'Pricing & Plans',
  description: 'Find the perfect plan for comparing LLM responses. Choose between our Starter and Premium tiers.',
};

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
      <div className="grid gap-6 grid-cols-1 md:grid-cols-3">
        {plans.map((plan) => (
          <Card key={plan.slug} className="border-amber-200 bg-white/90 p-6 shadow-[0_20px_50px_#70491c14] dark:border-slate-600 dark:bg-slate-800 flex flex-col justify-between">
            <div>
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
              <ul className="mt-6 space-y-2 text-sm text-slate-600 dark:text-slate-300">
                <li>• {plan.limits?.max_debates_per_month ?? "?"} {t("pricing.plan.debates")}</li>
                <li>• {plan.limits?.max_models_per_debate ?? 3} {t("pricing.plan.models")}</li>
                <li>
                  • {plan.limits?.exports_enabled ? t("pricing.plan.exportsEnabled") : t("pricing.plan.exportsDisabled")}
                </li>
              </ul>
            </div>
            <Button asChild className="mt-8 w-full bg-amber-600 text-white hover:bg-amber-700">
              <Link href={`/settings/billing?plan=${plan.slug}`}>{t("pricing.plan.cta")} {plan.name}</Link>
            </Button>
          </Card>
        ))}

        {/* Enterprise Tier Card */}
        <Card className="border-amber-400/80 bg-gradient-to-b from-amber-50/15 via-white to-white p-6 shadow-[0_20px_50px_#70491c1f] dark:border-amber-900/40 dark:from-slate-900 dark:to-slate-800 flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 bg-amber-600 text-white text-[9px] font-bold uppercase tracking-wider px-3 py-1 rounded-bl-xl">
            Custom
          </div>
          <div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-amber-600 dark:text-amber-400">Enterprise</p>
                <h2 className="heading-serif text-2xl text-slate-900 dark:text-white">Custom Tier</h2>
              </div>
              <div className="text-right text-2xl font-bold text-slate-900 dark:text-white">
                Contact Sales
              </div>
            </div>
            <ul className="mt-6 space-y-2 text-sm text-slate-600 dark:text-slate-300">
              <li>• Dedicated compute with zero rate limits</li>
              <li>• Private cloud / self-hosted database deploy</li>
              <li>• System audit export & retention controls</li>
              <li>• Custom integrations (Datadog, S3 logs)</li>
              <li>• SLA support & custom model integrations</li>
            </ul>
          </div>
          <Button asChild className="mt-8 w-full bg-slate-900 text-white hover:bg-slate-800 dark:bg-amber-600 dark:hover:bg-amber-700">
            <a href="mailto:enterprise@consultaion.com?subject=Enterprise%20Plan%20Inquiry">Contact Sales</a>
          </Button>
        </Card>
      </div>
    </main>
  );
}

