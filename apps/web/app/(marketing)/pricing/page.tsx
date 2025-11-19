import { getBillingPlans, type BillingPlanSummary } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export const revalidate = 3600;

async function fetchPlans(): Promise<BillingPlanSummary[]> {
  try {
    return await getBillingPlans();
  } catch {
    return [];
  }
}

export default async function PricingPage() {
  const plans = await fetchPlans();
  return (
    <main className="mx-auto max-w-5xl space-y-8 px-6 py-16">
      <div className="text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-700">Plans</p>
        <h1 className="heading-serif text-4xl text-[#3a2a1a]">Amber-Mocha Pricing</h1>
        <p className="mt-3 text-sm text-[#5a4a3a]">Choose the plan that matches your debate workload. Free users get 10 debates per month; Pro unlocks higher limits and exports.</p>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        {plans.map((plan) => (
          <Card key={plan.slug} className="border-amber-200 bg-white/90 p-6 shadow-[0_20px_50px_rgba(112,73,28,0.08)]">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-amber-600">{plan.is_default_free ? "Starter" : "Premium"}</p>
                <h2 className="heading-serif text-2xl text-[#3a2a1a]">{plan.name}</h2>
              </div>
              <div className="text-right text-3xl font-semibold text-[#3a2a1a]">
                {plan.price_monthly ? `$${plan.price_monthly.toFixed(2)}` : "Free"}
                <span className="text-xs font-normal text-stone-500">/mo</span>
              </div>
            </div>
            <ul className="mt-4 space-y-2 text-sm text-[#5a4a3a]">
              <li>• {plan.limits?.max_debates_per_month ?? "?"} debates / month</li>
              <li>• Up to {plan.limits?.max_models_per_debate ?? 3} models per debate</li>
              <li>• {plan.limits?.exports_enabled ? "Exports enabled" : "Exports disabled"}</li>
            </ul>
            <Button asChild className="mt-6 w-full bg-amber-600 text-white hover:bg-amber-700">
              <a href={`/settings/billing?plan=${plan.slug}`}>Choose {plan.name}</a>
            </Button>
          </Card>
        ))}
      </div>
    </main>
  );
}
