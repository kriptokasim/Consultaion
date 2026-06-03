"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, BarChart3, Trophy, Zap, MessageCircle, GitCompare, Scale } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { startDebate } from "@/lib/api";
import { PromotionArea } from "@/components/PromotionArea";
import { BillingLimitModal } from "@/components/billing/BillingLimitModal";
import { ApiClientError } from "@/lib/apiClient";
import type { DebateSummary } from "./types";
import { useI18n } from "@/lib/i18n/client";
import { trackEvent } from "@/lib/analytics";
import { OnboardingChecklist } from "@/components/dashboard/OnboardingChecklist";
import { OnboardingPanel } from "@/components/dashboard/OnboardingPanel";
import { ErrorBanner } from "@/components/errors/ErrorBanner";
import { ProviderHealthBanner } from "@/components/ui/provider-health-banner";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useDebatesList } from "@/lib/api/hooks/useDebatesList";
import { getBillingMe } from "@/lib/api";
import { apiRequest } from "@/lib/apiClient";
import { ModelSelector } from "@/components/dashboard/ModelSelector";
import { DashboardRunsHistory } from "@/components/dashboard/DashboardRunsHistory";
import { DashboardTemplatesSection } from "@/components/dashboard/DashboardTemplatesSection";

type ModelOption = {
  id: string;
  display_name: string;
  provider: string;
  tags: string[];
  max_context?: number | null;
  recommended: boolean;
  tier?: "standard" | "advanced";
};

export default function DashboardClient({ email, authToken }: { email?: string; authToken?: string }) {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [mode, setMode] = useState<"arena" | "conversation" | "compare" | "debate">("arena");
  const [compareModels, setCompareModels] = useState<string[]>([]);

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

  const [showModal, setShowModal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [limitModal, setLimitModal] = useState<{ open: boolean; code?: string }>({ open: false });
  const [modelError, setModelError] = useState<string | null>(null);

  // Onboarding state
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [templateUsed, setTemplateUsed] = useState(false);
  const [step3Reviewed, setStep3Reviewed] = useState(false);

  const [errorBanner, setErrorBanner] = useState<{
    type: "error" | "warning" | "timeout";
    title?: string;
    message: string;
  } | null>(null);

  const { data: debatesData, isLoading: debatesLoading } = useDebatesList();
  const debates = (debatesData?.items || []) as DebateSummary[];

  const { data: billing } = useQuery({
    queryKey: ["billing", "me"],
    queryFn: getBillingMe
  });

  // Fetch available AI models from /models/ endpoint
  const { data: modelsData } = useQuery({
    queryKey: ["models"],
    queryFn: async () => {
      try {
        return await apiRequest<{ models: any[] }>({ path: "/models/", method: "GET" });
      } catch {
        return { models: [] };
      }
    }
  });

  const models = (modelsData?.models || []).map((m: any) => ({
    id: m.id,
    display_name: m.display_name,
    provider: m.provider,
    tags: m.tags || [],
    recommended: m.recommended ?? false,
    tier: m.tier || "standard"
  })) as ModelOption[];

  useEffect(() => {
    if (models.length > 0 && !selectedModel) {
      const recommended = models.find(m => m.recommended);
      setSelectedModel(recommended?.id || models[0].id);
    }
  }, [models, selectedModel]);

  useEffect(() => {
    // Check if new user
    if (!debatesLoading && debates.length === 0) {
      setShowOnboarding(true);
    }
  }, [debatesLoading, debates.length]);

  const maxDebates = billing?.plan?.limits?.debates_per_month;
  const debatesUsed = billing?.usage?.debates_created ?? 0;
  const allowedTiers = ["standard", "advanced"]; // TODO: get from plan

  const handleDismissOnboarding = () => setShowOnboarding(false);
  const handleStep3Mark = () => setStep3Reviewed(true);

  const handleTemplateClick = (templateId: string) => {
    setTemplateUsed(true);
    setShowModal(true);
    // Prefill prompt based on template
    if (templateId === "strategy-saas-rollout") setPrompt(t("dashboard.templates.strategy.description"));
    else if (templateId === "risk-bank-governance") setPrompt(t("dashboard.templates.governance.description"));
    else if (templateId === "product-roadmap") setPrompt(t("dashboard.templates.product.description"));
  };

  // Draft persistence: restore on modal open
  // eslint-disable-next-line react-hooks/exhaustive-deps -- intentionally only trigger on modal open
  useEffect(() => {
    if (showModal) {
      const draft = localStorage.getItem('draft_prompt');
      if (draft && !prompt) setPrompt(draft);
    }
  }, [showModal]);

  // Draft persistence: save on prompt change
  useEffect(() => {
    if (prompt) {
      localStorage.setItem('draft_prompt', prompt);
    }
  }, [prompt]);

  // Create debate mutation using React Query
  const createDebateMutation = useMutation({
    mutationFn: async (params: { prompt: string; model_id?: string; locale: string; mode: string; compare_models?: string[] }) => {
      return startDebate(params);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['debates'] });
      setShowModal(false);
      setPrompt("");
      localStorage.removeItem('draft_prompt');
      window.location.href = `/runs/${data.id}`;
    },
    onError: (err) => {
      if (err instanceof ApiClientError) {
        if (err.status === 429) {
          const body = err.body as any;
          const kind = body?.kind === "tokens" ? t("quota.exceeded.tokens") : t("quota.exceeded.exports");
          setErrorBanner({
            type: "warning",
            title: t("quota.exceeded.title"),
            message: t("quota.exceeded.message", {
              used: body?.used ?? 0,
              limit: body?.limit ?? 0,
              kind
            }),
          });
          trackEvent("quota_exceeded", { kind: body?.kind, limit: body?.limit, used: body?.used, source: "debate_create" });
        } else if (err.status === 403 && (err.body as any)?.error === "account_disabled") {
          setErrorBanner({
            type: "error",
            title: t("errors.accountDisabled.title"),
            message: t("errors.accountDisabled"),
          });
          trackEvent("account_disabled_action_blocked", { action: "create_debate" });
        } else if (err.status === 402) {
          setLimitModal({ open: true, code: (err.body as any)?.code });
        } else {
          setErrorBanner({
            type: "error",
            message: err.message || t("errors.generic"),
          });
          trackEvent("debate_run_error_generic", { source: "debate_create", message: err.message });
        }
      } else {
        setErrorBanner({
          type: "error",
          message: t("errors.generic"),
        });
        trackEvent("debate_run_error_generic", { source: "debate_create", message: (err as Error).message });
      }
    },
  });

  const handleCreate = () => {
    if (!prompt.trim()) return;
    if (mode === "conversation" && !selectedModel) {
      setErrorBanner({
        type: "error",
        message: t("dashboard.errors.noModels"),
      });
      return;
    }
    if (mode === "compare" && compareModels.length < 2) {
      setErrorBanner({
        type: "error",
        message: "Please select at least 2 models to compare.",
      });
      return;
    }
    setErrorBanner(null);
    setError(null);
    createDebateMutation.mutate({
      prompt: prompt.trim(),
      model_id: mode === "conversation" ? selectedModel! : undefined,
      mode,
      compare_models: mode === "compare" ? compareModels : undefined,
      locale,
    });
  };

  const saving = createDebateMutation.isPending;

  return (
    <main className="space-y-10">
      {errorBanner && (
        <div className="mb-6">
          <ErrorBanner
            type={errorBanner.type}
            title={errorBanner.title}
            message={errorBanner.message}
            onDismiss={() => setErrorBanner(null)}
          />
        </div>
      )}
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
          <PrimaryCard icon={<Plus className="h-5 w-5" />} title={t("dashboard.cards.newDebate.title")} description={t("dashboard.cards.newDebate.description")} onClick={() => setShowModal(true)} />
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
              onNewDebate={() => setShowModal(true)}
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
      <DashboardRunsHistory debates={debates} debatesLoading={debatesLoading} onNewRun={() => setShowModal(true)} />

      {showModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 backdrop-blur-sm">
          <div className="flex flex-col w-full max-w-lg max-h-[85vh] rounded-2xl border border-border bg-card shadow-smooth-xl">
            {/* Header - Fixed */}
            <div className="flex-shrink-0 p-6 pb-2">
              <div className="space-y-2">
                <h3 className="heading-serif text-2xl font-semibold text-foreground">{t("dashboard.modal.title")}</h3>
                <p className="text-sm text-muted-foreground">{t("dashboard.modal.description")}</p>
              </div>
            </div>

            {/* Content - Scrollable */}
            <div className="flex-1 overflow-y-auto p-6 pt-2">
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-foreground" htmlFor="prompt">
                    {t("dashboard.modal.questionLabel")}
                  </label>
                  <Textarea
                    id="prompt"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                        e.preventDefault();
                        const canSubmit = prompt.trim() && !saving && modelError === null && !(mode === "conversation" && (!selectedModel && models.length > 0)) && !(mode === "compare" && compareModels.length < 2);
                        if (canSubmit) {
                          handleCreate();
                        }
                      }
                    }}
                    placeholder={t("dashboard.modal.placeholder")}
                    minLength={10}
                    maxLength={5000}
                    className="min-h-[140px] bg-background text-foreground"
                  />
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      {prompt.length} {t("dashboard.modal.characters")}
                    </span>
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-foreground">Mode</label>
                    <div className="space-y-2">
                      {/* Arena - Primary Option */}
                      <button
                        type="button"
                        onClick={() => setMode("arena")}
                        className={`w-full flex items-center gap-3 p-4 rounded-xl text-left border-2 transition-all ${
                          mode === "arena"
                            ? "border-primary bg-primary/5 shadow-sm"
                            : "border-border bg-card hover:bg-secondary/50"
                        }`}
                      >
                        <div className={`shrink-0 rounded-lg p-2 ${mode === "arena" ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"}`}>
                          <Zap className="h-5 w-5" />
                        </div>
                        <div className="min-w-0">
                          <p className={`font-semibold text-sm ${mode === "arena" ? "text-primary" : "text-foreground"}`}>
                            Arena — SOTA Comparison
                          </p>
                          <p className="text-xs text-muted-foreground">
                            4 top AI models answer, then a synthesizer gives the final verdict
                          </p>
                        </div>
                      </button>

                      {/* Secondary modes */}
                      <div className="grid grid-cols-3 gap-2">
                        <button type="button" onClick={() => setMode("conversation")} className={`flex flex-col items-center gap-1.5 p-3 rounded-xl text-center border transition-colors ${mode === "conversation" ? "border-primary bg-primary/5 text-primary" : "border-border bg-card text-muted-foreground hover:bg-secondary"}`}>
                          <MessageCircle className="h-4 w-4" />
                          <span className="text-xs font-medium">Conversation</span>
                        </button>
                        <button type="button" onClick={() => setMode("compare")} className={`flex flex-col items-center gap-1.5 p-3 rounded-xl text-center border transition-colors ${mode === "compare" ? "border-primary bg-primary/5 text-primary" : "border-border bg-card text-muted-foreground hover:bg-secondary"}`}>
                          <GitCompare className="h-4 w-4" />
                          <span className="text-xs font-medium">Compare</span>
                        </button>
                        <button type="button" onClick={() => setMode("debate")} className={`flex flex-col items-center gap-1.5 p-3 rounded-xl text-center border transition-colors ${mode === "debate" ? "border-primary bg-primary/5 text-primary" : "border-border bg-card text-muted-foreground hover:bg-secondary"}`}>
                          <Scale className="h-4 w-4" />
                          <span className="text-xs font-medium">Debate</span>
                        </button>
                      </div>
                    </div>
                  </div>

                  {mode === "arena" && (
                    <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm text-muted-foreground animate-in fade-in slide-in-from-top-2 duration-300">
                      <p className="font-medium text-foreground mb-1">⚡ How Arena works:</p>
                      <ol className="list-decimal list-inside space-y-0.5 text-xs">
                        <li>GPT-4o, Claude, Gemini, and DeepSeek all answer your question</li>
                        <li>Responses shown side-by-side with model branding</li>
                        <li>A synthesizer combines the strongest insights into a final verdict</li>
                      </ol>
                    </div>
                  )}

                  {mode === "conversation" && (
                    <div className="space-y-2 animate-in fade-in slide-in-from-top-2 duration-300">
                      <label className="text-sm font-semibold text-foreground" htmlFor="model">
                        {t("dashboard.modal.modelLabel")}
                      </label>
                      {modelError ? (
                        <p className="text-sm font-medium text-error">{modelError}</p>
                      ) : models.length > 0 ? (
                        <ModelSelector
                          models={models}
                          selectedModel={selectedModel}
                          onSelect={setSelectedModel}
                          allowedTiers={allowedTiers}
                        />
                      ) : (
                        <div className="rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm">
                          <p className="font-medium text-warning">{t("dashboard.errors.noModels")}</p>
                          <p className="mt-1 text-muted-foreground">{t("dashboard.errors.noModelsHint")}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {mode === "compare" && (
                    <div className="space-y-2 animate-in fade-in slide-in-from-top-2 duration-300">
                      <label className="text-sm font-semibold text-foreground">Select Models to Compare (Up to 4)</label>
                      <div className="grid grid-cols-2 gap-2">
                        {models.map(m => {
                          const isSelected = compareModels.includes(m.id);
                          return (
                            <button
                              key={m.id}
                              type="button"
                              onClick={() => {
                                if (isSelected) {
                                  setCompareModels(prev => prev.filter(id => id !== m.id));
                                } else if (compareModels.length < 4) {
                                  setCompareModels(prev => [...prev, m.id]);
                                }
                              }}
                              className={`flex flex-col items-start p-3 rounded-xl border text-left transition ${isSelected ? "border-primary bg-primary/5 ring-1 ring-primary" : "border-border bg-card hover:bg-secondary"} ${!isSelected && compareModels.length >= 4 ? "opacity-50 cursor-not-allowed" : ""}`}
                              disabled={!isSelected && compareModels.length >= 4}
                            >
                              <span className="font-medium text-sm text-foreground truncate w-full">{m.display_name}</span>
                              <span className="text-xs text-muted-foreground">{m.provider}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  {mode === "debate" && (
                    <div className="rounded-xl border border-border bg-secondary/50 p-4 text-sm text-muted-foreground animate-in fade-in slide-in-from-top-2 duration-300">
                      Debate mode runs the prompt through an AI Parliament (Optimist, Risk Officer, Architect) for structured adversarial critique and synthesis.
                    </div>
                  )}
                </div>
                {error ? <p className="text-sm font-medium text-error">{error}</p> : null}
              </div>
            </div>

            {/* Footer - Sticky */}
            <div className="flex-shrink-0 border-t border-border bg-card p-6 rounded-b-2xl">
              <div className="flex items-center justify-end gap-3">
                <Button variant="outline" onClick={() => setShowModal(false)} disabled={saving}>
                  {t("dashboard.modal.cancel")}
                </Button>
                <Button onClick={handleCreate} disabled={!prompt.trim() || saving || modelError !== null || (mode === "conversation" && (!selectedModel && models.length > 0)) || (mode === "compare" && compareModels.length < 2)}>
                  {saving ? t("dashboard.modal.creating") : t("dashboard.modal.submit")}
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <section>
        <PromotionArea location="dashboard_sidebar" />
      </section>

      <BillingLimitModal open={limitModal.open} code={limitModal.code} onClose={() => setLimitModal({ open: false })} />
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
