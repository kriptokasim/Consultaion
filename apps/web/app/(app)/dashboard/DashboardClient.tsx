"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Play, BarChart3, Trophy, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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

type ModelOption = {
  id: string;
  display_name: string;
  provider: string;
  tags: string[];
  max_context?: number | null;
  recommended: boolean;
  tier?: "standard" | "advanced";
};

function formatTimestamp(ts?: string | null) {
  if (!ts) return "Just now";
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "Just now";
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function statusTone(status?: string | null) {
  switch ((status || "").toLowerCase()) {
    case "running":
      return "bg-amber-100 text-amber-800 border-amber-200";
    case "completed":
    case "done":
      return "bg-emerald-100 text-emerald-800 border-emerald-200";
    case "queued":
    default:
      return "bg-stone-100 text-stone-800 border-stone-200";
  }
}

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useDebatesList } from "@/lib/api/hooks/useDebatesList";
import { getBillingMe } from "@/lib/api";

export default function DashboardClient({ email, authToken }: { email?: string; authToken?: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const [selectedModel, setSelectedModel] = useState<string | null>(null);

  // Fallback to reload if token was processed
  useEffect(() => {
    if (authToken && typeof window !== "undefined") {
      // 1. Save to localStorage for API clients
      localStorage.setItem("auth_token", authToken);

      // 2. Set 'consultaion_session' cookie for SSR (Cross-Origin Bootstrapping)
      // Note: Backend uses 'consultaion_session' cookie name (defined in Render env vars).
      // We duplicate it here on Frontend domain to allow SSR to see it.
      document.cookie = `consultaion_session=${authToken}; path=/; secure; samesite=lax; max-age=2592000`; // 30 days

      // 3. Clear URL and potentially reload to establish clean state
      const url = new URL(window.location.href);
      url.searchParams.delete("token");
      window.history.replaceState({}, "", url.toString());

      // Reload to retry SSR 'getMe' check now that cookie is set
      window.location.reload();
    }
  }, [authToken]);

  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
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

  // Assuming getMembers returns models/agents
  const { data: modelsData } = useQuery({
    queryKey: ["members"],
    queryFn: async () => {
      const res = await fetch("/api/config/members"); // Fallback if getMembers not exported or different
      if (!res.ok) return [];
      return res.json();
    }
  });

  const models = (modelsData?.items || []).map((m: any) => ({
    id: m.id,
    display_name: m.name,
    provider: m.provider,
    tags: m.tags || [],
    recommended: m.tags?.includes("recommended"),
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

  const handleCreate = async () => {
    if (!prompt.trim()) return;
    if (!selectedModel) {
      setErrorBanner({
        type: "error",
        message: t("dashboard.errors.noModels"),
      });
      return;
    }
    setSaving(true);
    setErrorBanner(null);
    setError(null); // Clear legacy error if any
    try {
      const { id } = await startDebate({ prompt: prompt.trim(), model_id: selectedModel });
      // Invalidate queries to refresh list
      queryClient.invalidateQueries({ queryKey: ['debates'] });

      setShowModal(false);
      setPrompt("");
      window.location.href = `/runs/${id}`;
    } catch (err) {
      if (err instanceof ApiClientError) {
        if (err.status === 429) {
          // Quota exceeded
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
          // Account disabled
          setErrorBanner({
            type: "error",
            title: t("errors.accountDisabled.title"),
            message: t("errors.accountDisabled"),
          });
          trackEvent("account_disabled_action_blocked", { action: "create_debate" });
        } else if (err.status === 402) {
          setLimitModal({ open: true, code: (err.body as any)?.code });
        } else {
          // Generic API error
          setErrorBanner({
            type: "error",
            message: err.message || t("errors.generic"),
          });
          trackEvent("debate_run_error_generic", { source: "debate_create", message: err.message });
        }
      } else {
        // Unexpected error
        setErrorBanner({
          type: "error",
          message: t("errors.generic"),
        });
        trackEvent("debate_run_error_generic", { source: "debate_create", message: (err as Error).message });
      }
    } finally {
      setSaving(false);
    }
  };

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
      <section className="rounded-3xl border border-amber-200/80 bg-gradient-to-br from-white via-[#fff7eb] to-[#f8e6c2] p-8 shadow-[0_24px_60px_rgba(112,73,28,0.12)]">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-amber-700">{t("dashboard.hero.kicker")}</p>
            <h1 className="heading-serif text-4xl font-semibold text-[#3a2a1a]">{t("dashboard.hero.title")}</h1>
            <p className="mt-2 max-w-2xl text-sm text-[#5a4a3a]">{t("dashboard.hero.description")}</p>
          </div>
          {email ? (
            <div className="ml-auto flex items-center gap-2 rounded-full border border-amber-200 bg-white/80 px-4 py-2 text-sm font-semibold text-amber-900 shadow-sm">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-100 text-amber-800">{email.charAt(0).toUpperCase()}</span>
              <span>{email}</span>
            </div>
          ) : null}
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <PrimaryCard icon={<Plus className="h-5 w-5" />} title={t("dashboard.cards.newDebate.title")} description={t("dashboard.cards.newDebate.description")} onClick={() => setShowModal(true)} />
          <LinkCard href="/analytics" icon={<BarChart3 className="h-5 w-5" />} title={t("dashboard.cards.analytics.title")} description={t("dashboard.cards.analytics.description")} />
          {maxDebates ? (
            <div className="flex flex-col justify-between rounded-2xl border border-amber-100/80 bg-white/90 p-5 shadow-[0_18px_36px_rgba(112,73,28,0.12)] transition-transform transition-shadow duration-200 hover:-translate-y-[2px] hover:shadow-lg">
              <div className="flex items-start gap-3">
                <span className="rounded-xl bg-amber-50 p-2 text-amber-800">
                  <Trophy className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-lg font-semibold text-[#3a2a1a]">Usage</p>
                  <p className="text-sm text-[#5a4a3a]">
                    {debatesUsed} / {maxDebates} debates used
                  </p>
                </div>
              </div>
              <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-amber-100">
                <div
                  className={`h-full rounded-full ${debatesUsed >= maxDebates ? "bg-red-500" : "bg-amber-500"}`}
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
                // Scroll to templates section
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

          <section id="templates-section" className="rounded-3xl border border-amber-200/70 bg-gradient-to-br from-white to-amber-50/30 p-8 shadow-md">
            <div className="mb-6 text-center">
              <h2 className="text-2xl font-semibold text-[#3a2a1a]">{t("dashboard.onboarding.title")}</h2>
              <p className="mt-2 text-sm text-[#5a4a3a]">{t("dashboard.onboarding.subtitle")}</p>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <TemplateCard
                title={t("dashboard.templates.strategy.title")}
                description={t("dashboard.templates.strategy.description")}
                onClick={() => handleTemplateClick("strategy-saas-rollout")}
              />
              <TemplateCard
                title={t("dashboard.templates.governance.title")}
                description={t("dashboard.templates.governance.description")}
                onClick={() => handleTemplateClick("risk-bank-governance")}
              />
              <TemplateCard
                title={t("dashboard.templates.product.title")}
                description={t("dashboard.templates.product.description")}
                onClick={() => handleTemplateClick("product-roadmap")}
              />
            </div>
          </section>
        </>
      )}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-amber-700">{t("dashboard.section.recent.kicker")}</p>
            <h2 className="heading-serif text-2xl font-semibold text-[#3a2a1a]">{t("dashboard.section.recent.title")}</h2>
          </div>
          <Link href="/runs" className="text-sm font-semibold text-amber-800 hover:text-amber-700">
            {t("dashboard.section.recent.link")}
          </Link>
        </div>
        {debates.length === 0 ? (
          <Card className="bg-white/90">
            <div className="space-y-3">
              <h3 className="heading-serif text-xl font-semibold text-[#3a2a1a]">{t("dashboard.empty.title")}</h3>
              <p className="text-sm text-[#5a4a3a]">{t("dashboard.empty.description")}</p>
              <Button variant="amber" className="px-5" onClick={() => setShowModal(true)}>
                {t("dashboard.empty.cta")}
              </Button>
            </div>
          </Card>
        ) : (
          <div className="overflow-hidden rounded-2xl border border-amber-200/70 bg-white/90 shadow-[0_18px_40px_rgba(112,73,28,0.12)]">
            <div className="divide-y divide-amber-100/80">
              {debates.map((debate) => {
                const replayAvailable = (debate.status || "").toLowerCase() === "completed" || (debate.status || "").toLowerCase() === "failed";
                return (
                  <Link
                    key={debate.id}
                    href={`/runs/${debate.id}`}
                    className="flex items-center gap-4 px-5 py-4 transition hover:bg-amber-50/70"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 text-amber-800 shadow-inner shadow-amber-900/10">
                      <Play className="h-5 w-5" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-[#3a2a1a] line-clamp-1">{debate.prompt || t("dashboard.prompt.untitled")}</p>
                      <p className="text-xs text-[#5a4a3a]">{t("dashboard.time.createdPrefix")} {formatTimestamp(debate.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {replayAvailable ? (
                        <Link href={`/runs/${debate.id}/replay`} className="text-xs font-semibold text-amber-700 underline-offset-4 hover:underline">
                          {t("dashboard.recentDebates.replay")}
                        </Link>
                      ) : null}
                      <Badge className={`border ${statusTone(debate.status)}`}>{debate.status ?? "queued"}</Badge>
                    </div>
                  </Link>
                )
              })}
            </div>
          </div>
        )}
      </section>

      {showModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-amber-200/80 bg-white p-6 shadow-[0_24px_60px_rgba(0,0,0,0.2)]">
            <div className="space-y-2">
              <h3 className="heading-serif text-2xl font-semibold text-[#3a2a1a]">{t("dashboard.modal.title")}</h3>
              <p className="text-sm text-[#5a4a3a]">{t("dashboard.modal.description")}</p>
            </div>
            <div className="mt-4 space-y-2">
              <label className="text-sm font-semibold text-[#3a2a1a]" htmlFor="prompt">
                {t("dashboard.modal.questionLabel")}
              </label>
              <Textarea
                id="prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder={t("dashboard.modal.placeholder")}
                minLength={10}
                maxLength={5000}
                className="min-h-[140px] bg-white text-[#3a2a1a]"
              />
              <div className="flex items-center justify-between text-xs text-stone-600">
                <span>
                  {prompt.length} {t("dashboard.modal.characters")}
                </span>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              <label className="text-sm font-semibold text-[#3a2a1a]" htmlFor="model">
                {t("dashboard.modal.modelLabel")}
              </label>
              {modelError ? (
                <p className="text-sm font-medium text-red-600">{modelError}</p>
              ) : models.length > 1 ? (
                <select
                  id="model"
                  className="w-full rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm text-amber-900 shadow-inner shadow-amber-900/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                  value={selectedModel ?? ""}
                  onChange={(e) => setSelectedModel(e.target.value)}
                >
                  {models.map((m) => {
                    const isAllowed = allowedTiers.includes(m.tier || "standard");
                    return (
                      <option key={m.id} value={m.id} disabled={!isAllowed}>
                        {m.display_name}
                        {m.recommended ? ` (${t("dashboard.modal.recommendedTag")})` : ""}
                        {!isAllowed ? " (Pro only)" : ""}
                      </option>
                    );
                  })}
                </select>
              ) : models.length === 1 ? (
                <div className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-900">
                  {t("dashboard.modal.singleModelLabel")} {models[0].display_name}
                </div>
              ) : null}
            </div>
            {error ? <p className="mt-2 text-sm font-medium text-red-600">{error}</p> : null}
            <div className="mt-6 flex items-center justify-end gap-3">
              <Button variant="outline" onClick={() => setShowModal(false)} disabled={saving}>
                {t("dashboard.modal.cancel")}
              </Button>
              <Button onClick={handleCreate} disabled={!prompt.trim() || saving || modelError !== null || (!selectedModel && models.length > 0)} className="shadow-[0_14px_32px_rgba(255,190,92,0.35)]">
                {saving ? t("dashboard.modal.creating") : t("dashboard.modal.submit")}
              </Button>
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
      className="group flex items-start gap-3 rounded-2xl border border-amber-300 bg-gradient-to-br from-amber-500 via-amber-400 to-amber-300 p-5 text-left shadow-[0_18px_36px_rgba(255,190,92,0.35)] transition-transform transition-shadow duration-200 hover:-translate-y-[2px] hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-600"
    >
      <span className="rounded-xl bg-white/20 p-2 text-amber-950 shadow-inner shadow-amber-900/20">{icon}</span>
      <div>
        <p className="text-lg font-semibold text-amber-950">{title}</p>
        <p className="text-sm text-amber-900/90">{description}</p>
      </div>
    </button>
  );
}

function LinkCard({ title, description, icon, href }: { title: string; description: string; icon: ReactNode; href: string }) {
  return (
    <Link
      href={href}
      className="flex items-start gap-3 rounded-2xl border border-amber-100/80 bg-white/90 p-5 text-left shadow-[0_18px_36px_rgba(112,73,28,0.12)] transition-transform transition-shadow duration-200 hover:-translate-y-[2px] hover:shadow-lg"
    >
      <span className="rounded-xl bg-amber-50 p-2 text-amber-800">{icon}</span>
      <div>
        <p className="text-lg font-semibold text-[#3a2a1a]">{title}</p>
        <p className="text-sm text-[#5a4a3a]">{description}</p>
      </div>
    </Link>
  );
}

function TemplateCard({ title, description, onClick }: { title: string; description: string; onClick: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col justify-between rounded-2xl border border-amber-200/70 bg-white/90 p-5 shadow-sm">
      <div>
        <h3 className="text-lg font-semibold text-[#3a2a1a] mb-2">{title}</h3>
        <p className="text-sm text-[#5a4a3a] mb-4">{description}</p>
      </div>
      <button
        type="button"
        onClick={onClick}
        className="w-full rounded-lg border-2 border-amber-400 bg-gradient-to-r from-amber-50 to-white px-4 py-2 text-sm font-semibold text-amber-900 transition hover:from-amber-100 hover:to-amber-50 hover:shadow-md"
      >
        {t("dashboard.templates.useTemplate")}
      </button>
    </div>
  );
}
