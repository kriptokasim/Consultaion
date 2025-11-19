"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BillingLimitModal } from "@/components/billing/BillingLimitModal";
import { PromotionArea } from "@/components/PromotionArea";
import { getBillingMe, getBillingPlans, createBillingCheckout, type BillingPlanSummary } from "@/lib/api";
import { ModelUsageChart } from "@/components/billing/ModelUsageChart";
import { ApiClientError } from "@/lib/apiClient";

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
    return <div className="p-8 text-sm text-[#5a4a3a]">Loading billing information...</div>;
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-10 md:flex-row">
      <div className="flex-1 space-y-4">
        <Card className="border-amber-200 bg-white/90 p-6">
          <p className="text-xs uppercase tracking-[0.2em] text-amber-700">Current plan</p>
          <h2 className="heading-serif text-3xl text-[#3a2a1a]">{billing.plan?.name ?? "Unknown"}</h2>
          <p className="mt-2 text-sm text-[#5a4a3a]">
            Period: {billing.usage?.period}. You have used {billing.usage?.debates_created ?? 0} debates so far.
          </p>
          {billing.plan?.limits?.max_debates_per_month ? (
            <div className="mt-4">
              <p className="text-xs text-stone-500">Debates this month</p>
              <div className="mt-2 h-2 w-full rounded-full bg-amber-100">
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
              <p className="mt-1 text-xs text-[#5a4a3a]">
                {billing.usage?.debates_created ?? 0} / {billing.plan.limits.max_debates_per_month} debates
              </p>
            </div>
          ) : null}
        </Card>

        <ModelUsageChart />

        <Card className="border-amber-200 bg-white/90 p-5">
          <h3 className="heading-serif text-xl text-[#3a2a1a]">Upgrade options</h3>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {plans.map((plan) => (
              <Card key={plan.slug} className="border border-amber-100 bg-white/80 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-amber-600">{plan.is_default_free ? "Free" : "Pro"}</p>
                <h4 className="heading-serif text-xl text-[#3a2a1a]">{plan.name}</h4>
                <p className="mt-1 text-xs text-[#5a4a3a]">{plan.limits?.max_debates_per_month ?? "?"} debates / month</p>
                <Button
                  className="mt-3 w-full bg-amber-600 text-white hover:bg-amber-700"
                  disabled={checkoutLoading === plan.slug}
                  onClick={() => handleCheckout(plan.slug)}
                >
                  {checkoutLoading === plan.slug ? "Preparing checkout..." : "Select"}
                </Button>
              </Card>
            ))}
          </div>
        </Card>
      </div>
      <div className="w-full max-w-sm space-y-4">
        <PromotionArea location="billing_sidebar" />
      </div>
      <BillingLimitModal open={limitModal.open} code={limitModal.code} onClose={() => setLimitModal({ open: false })} />
    </div>
  );
}
