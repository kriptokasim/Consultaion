"use client";

import React, { useMemo, useState } from "react";
import { Trophy, Sparkles, Bot, CheckCircle2, XCircle, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import type { DebateDetail, DebateEvent } from "@/lib/api/types";
import Image from "next/image";
import { ShareRunButton } from "@/components/debate/ShareRunButton";

/* ─── Extract a human-readable error from raw content ─── */
function extractFriendlyError(raw: string): { friendly: string; technical: string | null } {
    if (!raw) return { friendly: "This model did not return a response.", technical: null };

    const lower = raw.toLowerCase();

    if (lower.includes("credit balance is too low") || lower.includes("insufficient") || lower.includes("requires more credits"))
        return { friendly: "This provider's API credits have been exhausted. The account needs to be topped up.", technical: raw };

    if (lower.includes("api key not valid") || lower.includes("invalid api key") || lower.includes("authentication"))
        return { friendly: "The API key for this provider is invalid or expired.", technical: raw };

    if (lower.includes("rate limit") || lower.includes("429") || lower.includes("too many requests"))
        return { friendly: "This provider is temporarily rate-limited. Please try again in a moment.", technical: raw };

    if (lower.includes("timeout") || lower.includes("timed out"))
        return { friendly: "This model took too long to respond and was timed out.", technical: raw };

    if (lower.includes("error") || lower.includes("exception") || lower.includes("traceback") || lower.includes("failed"))
        return { friendly: "This model encountered an error while processing your request.", technical: raw };

    // Content looks normal — not an error
    return { friendly: "", technical: null };
}

/* ─── provider accent colours ─── */
const PROVIDER_COLORS: Record<string, { bg: string; border: string; text: string; accent: string; glow: string }> = {
    openai: {
        bg: "bg-emerald-50 dark:bg-emerald-950/30",
        border: "border-emerald-200 dark:border-emerald-800",
        text: "text-emerald-700 dark:text-emerald-300",
        accent: "bg-emerald-100 dark:bg-emerald-900/50",
        glow: "shadow-emerald-100/50 dark:shadow-emerald-900/30",
    },
    anthropic: {
        bg: "bg-orange-50 dark:bg-orange-950/30",
        border: "border-orange-200 dark:border-orange-800",
        text: "text-orange-700 dark:text-orange-300",
        accent: "bg-orange-100 dark:bg-orange-900/50",
        glow: "shadow-orange-100/50 dark:shadow-orange-900/30",
    },
    gemini: {
        bg: "bg-blue-50 dark:bg-blue-950/30",
        border: "border-blue-200 dark:border-blue-800",
        text: "text-blue-700 dark:text-blue-300",
        accent: "bg-blue-100 dark:bg-blue-900/50",
        glow: "shadow-blue-100/50 dark:shadow-blue-900/30",
    },
    openrouter: {
        bg: "bg-violet-50 dark:bg-violet-950/30",
        border: "border-violet-200 dark:border-violet-800",
        text: "text-violet-700 dark:text-violet-300",
        accent: "bg-violet-100 dark:bg-violet-900/50",
        glow: "shadow-violet-100/50 dark:shadow-violet-900/30",
    },
};

const DEFAULT_COLORS = {
    bg: "bg-slate-50 dark:bg-slate-900/30",
    border: "border-slate-200 dark:border-slate-700",
    text: "text-slate-700 dark:text-slate-300",
    accent: "bg-slate-100 dark:bg-slate-800",
    glow: "shadow-slate-100/50 dark:shadow-slate-800/30",
};

function getColors(provider?: string) {
    return PROVIDER_COLORS[provider || ""] || DEFAULT_COLORS;
}

/* ─── Logo component with fallback ─── */
function ModelLogo({ logoUrl, displayName, size = 28 }: { logoUrl?: string; displayName: string; size?: number }) {
    if (logoUrl) {
        return (
            <Image
                src={logoUrl}
                alt={displayName}
                width={size}
                height={size}
                className="rounded-md"
                unoptimized
            />
        );
    }
    return (
        <div
            className="flex items-center justify-center rounded-md bg-primary/10 text-primary font-bold"
            style={{ width: size, height: size, fontSize: size * 0.45 }}
        >
            {displayName.charAt(0)}
        </div>
    );
}

/* ─── Skeleton card while loading ─── */
function SkeletonCard({ index }: { index: number }) {
    const delays = ["", "animation-delay-150", "animation-delay-300", "animation-delay-500"];
    return (
        <div className={`flex flex-col rounded-2xl border border-border bg-card shadow-sm overflow-hidden opacity-60 ${delays[index] || ""}`}>
            <div className="p-4 border-b border-border flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-muted animate-pulse" />
                <div className="flex-1 space-y-1.5">
                    <div className="h-4 w-28 bg-muted animate-pulse rounded" />
                    <div className="h-3 w-20 bg-muted animate-pulse rounded" />
                </div>
            </div>
            <div className="p-5 space-y-2 flex-1">
                <div className="h-4 w-full bg-muted animate-pulse rounded" />
                <div className="h-4 w-5/6 bg-muted animate-pulse rounded" />
                <div className="h-4 w-4/6 bg-muted animate-pulse rounded" />
                <div className="h-4 w-3/4 bg-muted animate-pulse rounded" />
                <div className="h-4 w-2/3 bg-muted animate-pulse rounded" />
            </div>
        </div>
    );
}

/* ─── Main component ─── */
interface ArenaRunViewProps {
    debate: DebateDetail;
    events: DebateEvent[];
}

export default function ArenaRunView({ debate, events }: ArenaRunViewProps) {
    /* Parse arena events */
    const { modelResponses, synthesis } = useMemo(() => {
        const responses: Array<{
            model_id: string;
            display_name: string;
            provider: string;
            content: string;
            logo_url?: string;
            persona_type?: string;
            persona_tagline?: string;
            success: boolean;
        }> = [];
        let synthesisText = "";

        for (const evt of events) {
            if (evt.type === "arena_response") {
                const e = evt as any;
                responses.push({
                    model_id: e.model_id || "",
                    display_name: e.display_name || e.seat_name || "Model",
                    provider: e.provider || "",
                    content: e.content || e.text || "",
                    logo_url: e.logo_url,
                    persona_type: e.persona_type,
                    persona_tagline: e.persona_tagline,
                    success: e.success !== false,
                });
            } else if (evt.type === "arena_synthesis") {
                synthesisText = (evt as any).text || (evt as any).content || "";
            } else if (evt.type === "final" && !synthesisText) {
                synthesisText = (evt as any).text || "";
            }
        }

        // Fallback: if no arena events, try final_content from debate
        if (!synthesisText && debate.final_content) {
            synthesisText = debate.final_content;
        }

        // Fallback: try to extract model responses from final_meta
        if (responses.length === 0 && debate.final_meta?.models) {
            // Models info is in final_meta but content is in seat_message events
            const seatMessages = events.filter((e: any) => e.type === "seat_message");
            for (const model of debate.final_meta.models) {
                const matching = seatMessages.find((e: any) =>
                    (e as any).display_name === model.display_name ||
                    (e as any).seat_name === model.display_name
                );
                responses.push({
                    model_id: model.model_id,
                    display_name: model.display_name,
                    provider: model.provider,
                    content: (matching as any)?.content || (matching as any)?.text || "",
                    logo_url: model.logo_url,
                    persona_type: model.persona_type,
                    persona_tagline: model.persona_tagline,
                    success: model.success !== false,
                });
            }
        }

        return { modelResponses: responses, synthesis: synthesisText };
    }, [events, debate]);

    const isLoading = modelResponses.length === 0 && !synthesis;
    const expectedModels = debate.final_meta?.models?.length || 4;
    const [activeTab, setActiveTab] = useState<number>(0);

    return (
        <div className="flex flex-col gap-6 pb-8">
            {/* Question Banner */}
            <div className="rounded-2xl border border-border bg-gradient-to-br from-card via-card to-primary/5 p-6 shadow-sm">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 min-w-0">
                        <div className="shrink-0 rounded-xl bg-primary/10 p-2.5 text-primary">
                            <Sparkles className="h-5 w-5" />
                        </div>
                        <div className="min-w-0">
                            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                                Your Question
                            </p>
                            <p className="text-lg font-medium text-foreground leading-relaxed whitespace-pre-wrap">
                                {debate.prompt}
                            </p>
                        </div>
                    </div>
                    {/* Share Button */}
                    {debate.status === "completed" || debate.status === "completed_budget" ? (
                        <div className="shrink-0">
                            <ShareRunButton debateId={debate.id} initiallyPublic={(debate.config as any)?.is_public} />
                        </div>
                    ) : null}
                </div>
                {debate.final_meta?.successful_count != null && (
                    <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                            {debate.final_meta.successful_count}/{debate.final_meta.total_count} models responded
                        </span>
                    </div>
                )}
            </div>

            {/* Model Response Cards */}
            <div>
                <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-2">
                    <Bot className="h-4 w-4" />
                    Model Responses
                </h2>

                <div className="flex sm:hidden overflow-x-auto gap-2 pb-2 mb-4 custom-scrollbar">
                    {Array.from({ length: expectedModels }).map((_, i) => {
                        const resp = modelResponses[i];
                        if (!resp) {
                            return <div key={`skeleton-tab-${i}`} className="h-9 w-24 bg-muted animate-pulse rounded-xl shrink-0" />;
                        }
                        const colors = getColors(resp.provider);
                        const isActive = activeTab === i;
                        return (
                            <button
                                key={resp.model_id || i}
                                onClick={() => setActiveTab(i)}
                                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold border transition-all shrink-0 ${
                                    isActive
                                        ? `${colors.accent} ${colors.text} ${colors.border} shadow-sm scale-105`
                                        : "border-border bg-card text-muted-foreground hover:text-foreground"
                                }`}
                            >
                                <ModelLogo
                                    logoUrl={resp.logo_url}
                                    displayName={resp.display_name}
                                    size={14}
                                />
                                <span>{resp.display_name}</span>
                            </button>
                        );
                    })}
                </div>

                {/* Mobile View: Render only active card */}
                <div className="block sm:hidden">
                    {(() => {
                        const resp = modelResponses[activeTab];
                        if (!resp) return <SkeletonCard index={activeTab} />;
                        
                        const colors = getColors(resp.provider);
                        const errorInfo = !resp.success ? extractFriendlyError(resp.content) : null;
                        const isError = !resp.success && errorInfo;
                            return (
                                <article
                                    className={`flex flex-col rounded-2xl border ${colors.border} ${colors.bg} shadow-sm ${colors.glow} transition-all duration-200 overflow-hidden min-h-[350px]`}
                                    aria-label={`Response from ${resp.display_name}`}
                                >
                                    {/* Card Header */}
                                    <div className={`p-4 border-b ${colors.border} flex items-center gap-3`}>
                                        <div className={`shrink-0 rounded-xl ${colors.accent} p-2`}>
                                            <ModelLogo
                                                logoUrl={resp.logo_url}
                                                displayName={resp.display_name}
                                            />
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <div className="flex items-center gap-2">
                                                <p className={`font-semibold text-sm truncate ${colors.text}`}>
                                                    {resp.display_name}
                                                </p>
                                                {resp.success ? (
                                                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                                                ) : (
                                                    <XCircle className="h-3.5 w-3.5 shrink-0 text-red-500" />
                                                )}
                                            </div>
                                            {resp.persona_tagline && (
                                                <p className="text-xs text-muted-foreground truncate">
                                                    {resp.persona_tagline}
                                                </p>
                                            )}
                                        </div>
                                    </div>

                                    {/* Card Body */}
                                    {isError ? (
                                        <ErrorCardBody
                                            friendly={errorInfo.friendly}
                                            technical={errorInfo.technical}
                                            displayName={resp.display_name}
                                        />
                                    ) : (
                                        <div className="p-5 flex-1 overflow-y-auto max-h-[500px] prose prose-sm dark:prose-invert max-w-none custom-scrollbar">
                                            <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
                                                {resp.content || <span className="italic text-muted-foreground">No response received.</span>}
                                            </div>
                                        </div>
                                    )}
                                </article>
                            );
                    })()}
                </div>

                {/* Desktop View: Render grid of all cards */}
                <div className="hidden sm:grid grid-cols-2 xl:grid-cols-4 gap-4">
                    {Array.from({ length: expectedModels }).map((_, i) => {
                        const resp = modelResponses[i];
                        if (!resp) {
                            return <SkeletonCard key={`skeleton-card-${i}`} index={i} />;
                        }
                        
                        const colors = getColors(resp.provider);
                        const errorInfo = !resp.success ? extractFriendlyError(resp.content) : null;
                        const isError = !resp.success && errorInfo;
                        return (
                            <article
                                key={resp.model_id || i}
                                className={`flex flex-col rounded-2xl border ${colors.border} ${colors.bg} shadow-sm hover:shadow-md ${colors.glow} transition-all duration-200 overflow-hidden`}
                                aria-label={`Response from ${resp.display_name}`}
                            >
                                {/* Card Header */}
                                <div className={`p-4 border-b ${colors.border} flex items-center gap-3`}>
                                          <div className={`shrink-0 rounded-xl ${colors.accent} p-2`}>
                                              <ModelLogo
                                                  logoUrl={resp.logo_url}
                                                  displayName={resp.display_name}
                                              />
                                          </div>
                                          <div className="min-w-0 flex-1">
                                              <div className="flex items-center gap-2">
                                                  <p className={`font-semibold text-sm truncate ${colors.text}`}>
                                                      {resp.display_name}
                                                  </p>
                                                  {resp.success ? (
                                                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                                                  ) : (
                                                      <XCircle className="h-3.5 w-3.5 shrink-0 text-red-500" />
                                                  )}
                                              </div>
                                              {resp.persona_tagline && (
                                                  <p className="text-xs text-muted-foreground truncate">
                                                      {resp.persona_tagline}
                                                  </p>
                                              )}
                                          </div>
                                      </div>

                                      {/* Card Body */}
                                      {isError ? (
                                          <ErrorCardBody
                                              friendly={errorInfo.friendly}
                                              technical={errorInfo.technical}
                                              displayName={resp.display_name}
                                          />
                                      ) : (
                                          <div className="p-5 flex-1 overflow-y-auto max-h-[500px] prose prose-sm dark:prose-invert max-w-none custom-scrollbar">
                                              <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
                                                  {resp.content || <span className="italic text-muted-foreground">No response received.</span>}
                                              </div>
                                          </div>
                                      )}
                                  </article>
                              );
                          })}
                </div>
            </div>

            {/* Synthesis / Final Verdict */}
            {synthesis && (() => {
                const isSynthesisFailed = synthesis.startsWith("⚠️ Synthesis unavailable") || debate.final_meta?.synthesis_success === false;
                return (
                    <div className={`rounded-2xl border-2 shadow-lg ${isSynthesisFailed ? "border-amber-300 bg-amber-50/50 dark:border-amber-900/30 dark:bg-amber-950/10" : "border-primary/30 bg-gradient-to-br from-primary/5 via-card to-primary/5"} p-6`}>
                        <div className="flex items-center gap-3 mb-4">
                            <div className={`rounded-xl p-2.5 ${isSynthesisFailed ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" : "bg-primary/15 text-primary"}`}>
                                {isSynthesisFailed ? <AlertTriangle className="h-6 w-6" /> : <Trophy className="h-6 w-6" />}
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-foreground">
                                    {isSynthesisFailed ? "Synthesis Fallback" : "Final Verdict"}
                                </h2>
                                <p className="text-xs text-muted-foreground">
                                    {isSynthesisFailed
                                        ? "An error occurred during synthesis. Displaying top model response as fallback."
                                        : "Synthesized from the best insights of each model"}
                                </p>
                            </div>
                        </div>
                        <div className="prose prose-base dark:prose-invert max-w-none">
                            <div className="whitespace-pre-wrap leading-relaxed text-foreground">
                                {synthesis}
                            </div>
                        </div>

                        {/* Model attribution chips */}
                        {modelResponses.length > 0 && !isSynthesisFailed && (
                            <div className="mt-5 pt-4 border-t border-primary/10">
                                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                                    Contributing Models
                                </p>
                                <div className="flex flex-wrap gap-2">
                                    {modelResponses
                                        .filter((r) => r.success)
                                        .map((r) => {
                                            const colors = getColors(r.provider);
                                            return (
                                                <span
                                                    key={r.model_id}
                                                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${colors.accent} ${colors.text} border ${colors.border}`}
                                                >
                                                    <ModelLogo
                                                        logoUrl={r.logo_url}
                                                        displayName={r.display_name}
                                                        size={14}
                                                    />
                                                    {r.display_name}
                                                </span>
                                            );
                                        })}
                                </div>
                            </div>
                        )}
                    </div>
                );
            })()}

            {/* Loading synthesis indicator */}
            {modelResponses.length > 0 && !synthesis && (
                <div className="rounded-2xl border border-dashed border-primary/30 bg-primary/5 p-6 flex items-center gap-4">
                    <div className="rounded-xl bg-primary/15 p-2.5 text-primary">
                        <Trophy className="h-6 w-6 animate-pulse" />
                    </div>
                    <div>
                        <p className="font-semibold text-foreground">Synthesizing Final Verdict…</p>
                        <p className="text-sm text-muted-foreground">
                            Combining the strongest insights from {modelResponses.filter(r => r.success).length} models
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}

/* ─── Friendly error card body ─── */
function ErrorCardBody({ friendly, technical, displayName }: { friendly: string; technical: string | null; displayName: string }) {
    const [showDetails, setShowDetails] = useState(false);
    return (
        <div className="p-5 flex-1 flex flex-col items-center justify-center text-center gap-3">
            <div className="rounded-full bg-red-100 dark:bg-red-900/30 p-3">
                <AlertTriangle className="h-6 w-6 text-red-500 dark:text-red-400" />
            </div>
            <div>
                <p className="text-sm font-medium text-foreground">{displayName} Unavailable</p>
                <p className="mt-1 text-xs text-muted-foreground leading-relaxed max-w-[240px] mx-auto">
                    {friendly}
                </p>
            </div>
            {technical && (
                <button
                    type="button"
                    onClick={() => setShowDetails(!showDetails)}
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground/70 hover:text-muted-foreground transition-colors"
                >
                    {showDetails ? "Hide" : "Show"} details
                    {showDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                </button>
            )}
            {showDetails && technical && (
                <pre className="mt-1 w-full max-h-32 overflow-auto rounded-lg bg-muted/50 p-2 text-[10px] text-muted-foreground text-left whitespace-pre-wrap break-all">
                    {technical.slice(0, 500)}{technical.length > 500 ? "…" : ""}
                </pre>
            )}
        </div>
    );
}
