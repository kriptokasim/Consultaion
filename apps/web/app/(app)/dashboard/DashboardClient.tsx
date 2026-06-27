"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, BarChart3, Trophy } from "lucide-react";
import { PromotionArea } from "@/components/PromotionArea";
import type { DebateSummary } from "@/lib/api/types";
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

export default function DashboardClient({ email }: { email?: string }) {
  const { t } = useI18n();
  const router = useRouter();

  // Onboarding state
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [templateUsed, setTemplateUsed] = useState(false);
  const [step3Reviewed, setStep3Reviewed] = useState(false);

  const { data: debatesData, isLoading: debatesLoading } = useDebatesList();
  const debates = debatesData?.items || [];

  const { data: billing } = useQuery({
    queryKey: ["billing", "me"],
    queryFn: getBillingMe
  });

  // FH109: Direct first-run activation — redirect zero-runs users to live composer
  useEffect(() => {
    if (!debatesLoading && debates.length === 0) {
      const redirectEnabled = process.env.NEXT_PUBLIC_FIRST_RUN_LIVE_REDIRECT_ENABLED !== "false";
      if (redirectEnabled) {
        trackEvent("first_run_redirect_to_live");
        router.replace("/live?focus=prompt");
        return;
      }
      setShowOnboarding(true);
    }
  }, [debatesLoading, debates.length, router]);

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
        {debates.length > 0 ? (
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            <div className="md:col-span-2 space-y-6">
              <div className="bg-background/50 backdrop-blur rounded-2xl border border-border/60 p-1">
                <div className="relative flex items-center">
                  <input 
                    type="text" 
                    placeholder="Ask a new question to start an Arena run..." 
                    className="w-full bg-transparent text-sm px-4 py-3 outline-none"
                    onKeyDown={(e) => {
                      if(e.key === 'Enter' && e.currentTarget.value.trim()) {
                        router.push(`/live?prefill_prompt=${encodeURIComponent(e.currentTarget.value)}`)
                      }
                    }}
                  />
                  <button 
                    onClick={(e) => {
                      const input = e.currentTarget.previousElementSibling as HTMLInputElement;
                      if(input?.value.trim()) router.push(`/live?prefill_prompt=${encodeURIComponent(input.value)}`);
                      else router.push("/live?focus=prompt");
                    }}
                    className="shrink-0 bg-primary text-primary-foreground h-8 w-8 rounded-xl flex items-center justify-center mr-1 shadow-sm hover:opacity-90 transition-opacity"
                  >
                    <Plus className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Latest Run Card */}
              {debates[0] && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-foreground px-1">Latest Run</h3>
                  <Link 
                    href={`/runs/${debates[0].id}`}
                    className="block bg-card hover:bg-card/80 border border-border shadow-sm hover:shadow-md transition-all duration-200 rounded-2xl p-5"
                  >
                    <div className="flex justify-between items-start gap-4">
                      <p className="font-medium text-foreground line-clamp-2 leading-relaxed">{debates[0].prompt}</p>
                      <span className="shrink-0 inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                        {debates[0].status}
                      </span>
                    </div>
                    <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
                      <span>{debates[0].created_at ? new Date(debates[0].created_at).toLocaleDateString() : 'Unknown date'}</span>
                      <span>{debates[0].models_expected || 4} models</span>
                    </div>
                  </Link>
                </div>
              )}
            </div>
            
            <div className="space-y-4">
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
                        {debatesUsed} / {maxDebates} debates
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
          </div>
        ) : (
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
        )}
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
