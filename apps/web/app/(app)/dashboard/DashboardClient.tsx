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

type ModelOption = {
  id: string;
  display_name: string;
  provider: string;
  tags: string[];
  max_context?: number | null;
  recommended: boolean;
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

export default function DashboardClient({ initialDebates, email }: { initialDebates: DebateSummary[]; email?: string | null }) {
  const { t } = useI18n();
  const [showModal, setShowModal] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [debates, setDebates] = useState<DebateSummary[]>(initialDebates);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelError, setModelError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [limitModal, setLimitModal] = useState<{ open: boolean; code?: string }>({ open: false });
  const formatTimestamp = (ts?: string | null) => {
    if (!ts) return t("dashboard.time.justNow");
    const date = new Date(ts);
    if (Number.isNaN(date.getTime())) return t("dashboard.time.justNow");
    return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  };

  useEffect(() => {
    let cancelled = false;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${apiBase}/models`, { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        const items: ModelOption[] = Array.isArray(data?.models) ? data.models : [];
        setModels(items);
        const recommended = items.find((m) => m.recommended) || items[0];
        setSelectedModel(recommended ? recommended.id : null);
        if (!items.length) {
          setModelError(t("dashboard.errors.noModelsAdmin"));
        }
      })
      .catch(() => {
        if (cancelled) return;
        setModelError(t("dashboard.errors.loadModels"));
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  const handleCreate = async () => {
    if (!prompt.trim()) return;
    if (!selectedModel) {
      setError(t("dashboard.errors.noModels"));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const { id } = await startDebate({ prompt: prompt.trim(), model_id: selectedModel });
      const entry: DebateSummary = {
        id,
        prompt: prompt.trim(),
        status: "queued",
        created_at: new Date().toISOString(),
      };
      setDebates((prev) => [entry, ...prev].slice(0, 12));
      setShowModal(false);
      setPrompt("");
      window.location.href = `/runs/${id}`;
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 402) {
        setLimitModal({ open: true, code: (err.body as any)?.code });
      } else {
        setError(err instanceof Error ? err.message : t("dashboard.errors.create"));
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="space-y-10">
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
          <LinkCard href="/leaderboard" icon={<Trophy className="h-5 w-5" />} title={t("dashboard.cards.leaderboard.title")} description={t("dashboard.cards.leaderboard.description")} />
        </div>
      </section>

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
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name} {m.recommended ? `(${t("dashboard.modal.recommendedTag")})` : ""}
                    </option>
                  ))}
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
