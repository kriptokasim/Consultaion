"use client";

import React, { useMemo, useState } from "react";
import { Sparkles, Bot, CheckCircle2 } from "lucide-react";
import type { DebateDetail, DebateEvent } from "@/lib/api/types";
import { ShareRunButton } from "@/components/debate/ShareRunButton";
import { ModelCard, ModelLogo, SkeletonCard, getColors } from "./ModelCard";
import type { ModelResponse } from "./ModelCard";
import { SynthesisCard, SynthesisLoading } from "./SynthesisCard";
import { PublicRunCTATop, PublicRunCTAFooter } from "./CTABanner";
import { DivergenceMeter } from "./DivergenceMeter";
import { SynthesisReveal } from "./SynthesisReveal";

/* ─── Main component ─── */
interface ArenaRunViewProps {
    debate: DebateDetail;
    events: DebateEvent[];
    profile?: any;
}

export default function ArenaRunView({ debate, events, profile }: ArenaRunViewProps) {
    /* Parse arena events */
    const { modelResponses, synthesis } = useMemo(() => {
        const responses: Array<ModelResponse> = [];
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
            {!profile && (
                <PublicRunCTATop debateId={debate.id} />
            )}

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
                    {(debate.status === "completed" || debate.status === "completed_budget") && profile && (!debate.user_id || profile.id === debate.user_id) ? (
                        <div className="shrink-0">
                            <ShareRunButton 
                                debateId={debate.id} 
                                initiallyPublic={(debate.config as any)?.is_public} 
                                modelCount={expectedModels}
                                hasSynthesis={!!synthesis}
                            />
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

                <div role="tablist" aria-label="Model responses" className="flex sm:hidden overflow-x-auto gap-2 pb-2 mb-4 custom-scrollbar">
                    {Array.from({ length: expectedModels }).map((_, i) => {
                        const resp = modelResponses[i];
                        if (!resp) {
                            return <div key={`skeleton-tab-${i}`} className="h-9 w-24 bg-muted animate-pulse rounded-xl shrink-0" />;
                        }
                        const colors = getColors(resp.provider);
                        const isActive = activeTab === i;
                        const tabId = `model-tab-${resp.model_id || i}`;
                        const panelId = `model-panel-${resp.model_id || i}`;
                        return (
                            <button
                                key={resp.model_id || i}
                                role="tab"
                                id={tabId}
                                aria-selected={isActive}
                                aria-controls={panelId}
                                tabIndex={isActive ? 0 : -1}
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
                <div role="tabpanel" id={`model-panel-${modelResponses[activeTab]?.model_id || activeTab}`} aria-labelledby={`model-tab-${modelResponses[activeTab]?.model_id || activeTab}`} className="block sm:hidden">
                    {(() => {
                        const resp = modelResponses[activeTab];
                        if (!resp) return <SkeletonCard index={activeTab} />;
                        return <ModelCard resp={resp} className="min-h-[350px]" />;
                    })()}
                </div>

                {/* Desktop View: Render grid of all cards */}
                <div className="hidden sm:grid grid-cols-2 xl:grid-cols-4 gap-4">
                    {Array.from({ length: expectedModels }).map((_, i) => {
                        const resp = modelResponses[i];
                        if (!resp) {
                            return <SkeletonCard key={`skeleton-card-${i}`} index={i} />;
                        }
                        return <ModelCard key={resp.model_id || i} resp={resp} />;
                    })}
                </div>
            </div>

            {/* Claims Divergence Analysis */}
            <DivergenceMeter 
                debateId={debate.id} 
                isCompleted={debate.status === "completed" || debate.status === "completed_budget"} 
            />

            {/* Synthesis / Final Verdict */}
            {synthesis && (() => {
                const isSynthesisFailed = synthesis.startsWith("⚠️ Synthesis unavailable") || debate.final_meta?.synthesis_success === false;
                return (
                    <SynthesisReveal 
                        synthesis={synthesis} 
                        modelResponses={modelResponses} 
                        isSynthesisFailed={isSynthesisFailed} 
                        debateId={debate.id}
                    />
                );
            })()}

            {/* Loading synthesis indicator */}
            {modelResponses.length > 0 && !synthesis && (
                <SynthesisLoading successfulCount={modelResponses.filter(r => r.success).length} />
            )}

            {!profile && debate.status === "completed" && (
                <PublicRunCTAFooter debateId={debate.id} />
            )}
        </div>
    );
}
