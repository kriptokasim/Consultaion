"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, BarChart3, Trophy } from "lucide-react";
import { PromotionArea } from "@/components/PromotionArea";
import type { DebateSummary } from "./types";
import { useI18n } from "@/lib/i18n/client";
import { trackEvent } from "@/lib/analytics";
import { OnboardingChecklist } from "@/components/dashboard/OnboardingChecklist";
import { OnboardingPanel } from "@/components/dashboard/OnboardingPanel";
import { ProviderHealthBanner } from "@/components/ui/provider-health-banner";
import { useQuery } from "@tanstack/react-query";
import { useDebatesList } from "@/lib/api/hooks/useDebatesList";
import { getBillingMe } from "@/lib/api";
import { DashboardRunsHistory } from "@/components/dashboard/DashboardRunsHistory";
import { DashboardTemplatesSection } from "@/components/dashboard/DashboardTemplatesSection";

export default function DashboardClient({ email, authToken }: { email?: string; authToken?: string }) {
  const { t } = useI18n();
  const router = useRouter();

  // Bootstrap: process token from Google OAuth redirect
  useEffect(() => {
    if (authToken && typeof window !== "undefined") {
      // Set 'consultaion_session' cookie for SSR cross-origin bootstrapping.
      document.cookie = `consultaion_session=${authToken}; path=/; secure; samesite=lax; max-age=2592000`; // 30 days

      // Strip token from URL to prevent leakage via browser history / referrers
      const url = new URL(window.location.href);
      url.searchParams.delete("token");
      window.history.replaceState({}, "", url.toString());

      // Reload so SSR 'getMe' can see the newly set cookie
      window.location.reload();
    }
  }, [authToken]);

  // Onboarding state
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [templateUsed, setTemplateUsed] = useState(false);
  const [step3Reviewed, setStep3Reviewed] = useState(false);

  const { data: debatesData, isLoading: debatesLoading } = useDebatesList();
  const debates = (debatesData?.items || []) as DebateSummary[];

  const { data: billing } = useQuery({
    queryKey: ["billing", "me"],
    queryFn: getBillingMe
  });

  useEffect(() => {
    if (!debatesLoading && debates.length === 0) {
      setShowOnboarding(true);
    }
  }, [debatesLoading, debates.length]);

  const maxDebates = billing?.plan?.limits?.debates_per_month;
  const debatesUsed = billing?.usage?.debates_created ?? 0;

  const handleDismissOnboarding = () => setShowOnboarding(false);
  const handleStep3Mark = () => setStep3Reviewed(true);

  const handleTemplateClick = (templateId: string) => {
    setTemplateUsed(true);
    let text = "";
    if (templateId === "strategy-saas-rollout") text = t("dashboard.templates.strategy.description");
    else if (templateId === "risk-bank-governance") text = t("dashboard.templates.governance.description");
    else if (templateId === "product-roadmap") text = t("dashboard.templates.product.description");
    
    trackEvent("overview_template_clicked", { template_id: templateId });
    router.push(`/live?prefill_prompt=${encodeURIComponent(text)}`);
  };

  return (
    <main className="space-y-10">
      <ProviderHealthBanner className="mb-6" />
      <section className="rounded-3xl border border-border bg-gradient-to-br from-card via-secondary to-blue-50 p-8 shadow-smooth dark:to-secondary">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-accent-secondary">{t("dashboard.hero.kicker")}</p>
            <h1 className="heading-serif text-4xl font-semibold text-foreground">{t("dashboard.hero.title")}</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{t("dashboard.hero.description")}</p>
          </div>
          {email ? (
            <div className="ml-auto flex items-center gap-2 rounded-full border border-border bg-card/80 px-4 py-2 text-sm font-semibold text-foreground shadow-sm">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">{email.charAt(0).toUpperCase()}</span>
              <span>{email}</span>
            </div>
          ) : null}
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <PrimaryCard icon={<Plus className="h-5 w-5" />} title={t("dashboard.cards.newDebate.title")} description={t("dashboard.cards.newDebate.description")} onClick={() => { trackEvent("overview_go_to_arena_clicked"); router.push("/live?focus=prompt"); }} />
          <LinkCard href="/analytics" icon={<BarChart3 className="h-5 w-5" />} title={t("dashboard.cards.analytics.title")} description={t("dashboard.cards.analytics.description")} />
          {maxDebates ? (
            <div className="flex flex-col justify-between rounded-2xl border border-border bg-card p-5 shadow-smooth transition-transform transition-shadow duration-200 hover:-translate-y-[2px] hover:shadow-smooth-lg">
              <div className="flex items-start gap-3">
                <span className="rounded-xl bg-accent-secondary/10 p-2 text-accent-secondary">
                  <Trophy className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-lg font-semibold text-foreground">Usage</p>
                  <p className="text-sm text-muted-foreground">
                    {debatesUsed} / {maxDebates} debates used
                  </p>
                </div>
              </div>
              <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className={`h-full rounded-full ${debatesUsed >= maxDebates ? "bg-error" : "bg-accent-secondary"}`}
                  style={{ width: `${Math.min((debatesUsed / maxDebates) * 100, 100)}%` }}
                />
              </div>
            </div>
          ) : (
            <LinkCard href="/leaderboard" icon={<Trophy className="h-5 w-5" />} title={t("dashboard.cards.leaderboard.title")} description={t("dashboard.cards.leaderboard.description")} />
          )}
        </div>
      </section>

      {/* Onboarding Templates - Show only for first-time users */}
      {debates.length === 0 && (
        <>
          {showOnboarding && (
            <OnboardingPanel
              onDismiss={handleDismissOnboarding}
              onOpenTemplates={() => {
                document.getElementById("templates-section")?.scrollIntoView({ behavior: "smooth" });
              }}
              onNewDebate={() => router.push("/live?focus=prompt")}
            />
          )}

          {/* Onboarding Checklist */}
          <OnboardingChecklist
            step1Complete={templateUsed}
            step2Complete={debates.length > 0}
            step3Complete={step3Reviewed}
            onStep3Mark={handleStep3Mark}
          />

          {/* Onboarding Templates Section */}
          <DashboardTemplatesSection onTemplateUse={handleTemplateClick} />
        </>
      )}

      {/* Runs History Section */}
      <DashboardRunsHistory debates={debates} debatesLoading={debatesLoading} onNewRun={() => router.push("/live?focus=prompt")} />

      <section>
        <PromotionArea location="dashboard_sidebar" />
      </section>
    </main>
  );
}

function PrimaryCard({ title, description, icon, onClick }: { title: string; description: string; icon: ReactNode; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex items-center md:items-start gap-3 rounded-2xl border border-primary bg-primary p-3 md:p-5 text-left text-primary-foreground shadow-smooth-lg transition-transform transition-shadow duration-200 hover:-translate-y-[2px] hover:shadow-smooth-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
    >
      <span className="shrink-0 rounded-xl bg-white/20 p-2 shadow-inner">{icon}</span>
      <div className="min-w-0">
        <p className="text-base md:text-lg font-semibold truncate">{title}</p>
        <p className="hidden md:block text-sm opacity-80">{description}</p>
      </div>
    </button>
  );
}

function LinkCard({ title, description, icon, href }: { title: string; description: string; icon: ReactNode; href: string }) {
  return (
    <Link
      href={href}
      className="flex items-center md:items-start gap-3 rounded-2xl border border-border bg-card p-3 md:p-5 text-left shadow-smooth transition-transform transition-shadow duration-200 hover:-translate-y-[2px] hover:shadow-smooth-lg"
    >
      <span className="shrink-0 rounded-xl bg-primary/10 p-2 text-primary">{icon}</span>
      <div className="min-w-0">
        <p className="text-base md:text-lg font-semibold text-foreground truncate">{title}</p>
        <p className="hidden md:block text-sm text-muted-foreground">{description}</p>
      </div>
    </Link>
  );
}
