"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BillingLimitModal } from "@/components/billing/BillingLimitModal";
import { PromotionArea } from "@/components/PromotionArea";
import { getBillingMe, getBillingPlans, createBillingCheckout, type BillingPlanSummary } from "@/lib/api";
import { ModelUsageChart } from "@/components/billing/ModelUsageChart";
import { ApiClientError } from "@/lib/apiClient";
import { useI18n } from "@/lib/i18n/client";

interface BillingState {
  plan?: BillingPlanSummary;
  usage?: {
    period: string;
    debates_created: number;
    exports_count: number;
    tokens_used: number;
  };
}

export default function BillingSettingsClient() {
  const [billing, setBilling] = useState<BillingState>({});
  const [plans, setPlans] = useState<BillingPlanSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [limitModal, setLimitModal] = useState<{ open: boolean; code?: string }>({ open: false });
  const { t } = useI18n();

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const [me, planList] = await Promise.all([getBillingMe(), getBillingPlans()]);
        if (!mounted) return;
        setBilling(me);
        setPlans(planList);
      } catch (err) {
        console.error("Failed to load billing", err);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, []);

  const handleCheckout = async (slug: string) => {
    try {
      setCheckoutLoading(slug);
      const { checkout_url } = await createBillingCheckout(slug);
      window.location.href = checkout_url;
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 402) {
        setLimitModal({ open: true, code: err.body?.code });
      }
    } finally {
      setCheckoutLoading(null);
    }
  };

  if (loading) {
    return <div className="p-8 text-sm text-slate-600 dark:text-slate-300">{t("settings.billing.loading")}</div>;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-6 py-10">
      <div className="flex-1 space-y-4">
        <Card className="border-slate-200 dark:border-slate-700 bg-white/90 dark:bg-slate-800 p-6">
          <p className="text-xs uppercase tracking-[0.2em] text-amber-700 dark:text-amber-400">{t("settings.billing.currentPlan")}</p>
          <h2 className="heading-serif text-3xl text-slate-900 dark:text-white">{billing.plan?.name ?? t("settings.billing.planUnknown")}</h2>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
            {t("settings.billing.periodLabel")} {billing.usage?.period ?? t("settings.billing.periodUnknown")}.{" "}
            {t("settings.billing.usagePrefix")} {billing.usage?.debates_created ?? 0} {t("settings.billing.debateSuffix")}
          </p>
          {billing.plan?.limits?.max_debates_per_month ? (
            <div className="mt-4">
              <p className="text-xs text-slate-500 dark:text-slate-400">{t("settings.billing.debatesThisMonth")}</p>
              <div className="mt-2 h-2 w-full rounded-full bg-slate-100 dark:bg-slate-700">
                <div
                  className="h-full rounded-full bg-amber-500"
                  style={{
                    width: `${Math.min(
                      100,
                      Math.round(((billing.usage?.debates_created ?? 0) / billing.plan.limits.max_debates_per_month) * 100),
                    )}%`,
                  }}
                />
              </div>
              <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                {billing.usage?.debates_created ?? 0} / {billing.plan.limits.max_debates_per_month} {t("settings.billing.debateProgress")}
              </p>
            </div>
          ) : null}
        </Card>

        <ModelUsageChart />

        <Card className="border-slate-200 dark:border-slate-700 bg-white/90 dark:bg-slate-800 p-5">
          <h3 className="heading-serif text-xl text-slate-900 dark:text-white">{t("settings.billing.upgradeTitle")}</h3>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {plans.map((plan) => (
              <Card key={plan.slug} className="border border-slate-200 dark:border-slate-600 bg-white/80 dark:bg-slate-800 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-amber-700 dark:text-amber-400">{plan.is_default_free ? t("settings.billing.planBadge.free") : t("settings.billing.planBadge.pro")}</p>
                <h4 className="heading-serif text-xl text-slate-900 dark:text-white">{plan.name}</h4>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                  {plan.limits?.max_debates_per_month ?? "?"} {t("settings.billing.planLimitLabel")}
                </p>
                <Button
                  className="mt-3 w-full"
                  disabled={checkoutLoading === plan.slug}
                  onClick={() => handleCheckout(plan.slug)}
                >
                  {checkoutLoading === plan.slug ? t("settings.billing.preparing") : t("settings.billing.select")}
                </Button>
              </Card>
            ))}
          </div>
        </Card>
      </div>
      <BillingLimitModal open={limitModal.open} code={limitModal.code} onClose={() => setLimitModal({ open: false })} />
    </div>
  );
}
