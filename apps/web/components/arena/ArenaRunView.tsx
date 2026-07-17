"use client";

import React, { useMemo, useState } from "react";
import { Sparkles, Bot, CheckCircle2, Eye, MessageSquare, Shield, AlertTriangle, RefreshCw, ChevronRight } from "lucide-react";
import type { DebateDetail, DebateEvent, PersistedModelResponse } from "@/lib/api/types";
import { getArenaSynthesisArtifacts } from "@/lib/arena/synthesisArtifacts";
import { ShareRunButton } from "@/components/debate/ShareRunButton";
import { ModelCard, StreamingModelCard, SkeletonCard } from "./ModelCard";
import type { ModelResponse } from "./ModelCard";
import type { StreamingModelBuffer } from "@/lib/streaming/types";
import type { ResponsesState, TimelineState } from "@/hooks/useRunWorkspace";
import { SynthesisLoading } from "./SynthesisCard";
import { PublicRunCTATop, PublicRunCTAFooter } from "./CTABanner";
import { DivergenceMeter } from "./DivergenceMeter";
import { SynthesisReveal } from "./SynthesisReveal";
import { DecisionReportView } from "@/components/report/DecisionReportView";
import { fetchWithAuth } from "@/lib/auth";
import { useCardKeyboardNav } from "@/hooks/useCardKeyboardNav";
import { buildArenaSlots } from "@/lib/arena/buildArenaSlots";

/* ─── Main component ─── */
interface ArenaRunViewProps {
    debate: DebateDetail;
    events: DebateEvent[];
    responses?: PersistedModelResponse[];
    streamingBuffers?: Map<string, StreamingModelBuffer>;
    isTerminal?: boolean;
    responsesState?: ResponsesState;
    responsesError?: string | null;
    timelineState?: TimelineState;
    presentation?: "historical" | "live";
    profile?: any;
    onRefetch?: () => Promise<any> | void;
}

export default function ArenaRunView({ debate, events, responses: persistedResponses, streamingBuffers, isTerminal, responsesState, responsesError, timelineState, presentation = "historical", profile, onRefetch }: ArenaRunViewProps) {
    /* Parse arena events */
    const { modelResponses, synthesis } = useMemo(() => {
        const eventResponses: Array<ModelResponse> = [];
        let synthesisText = "";

        // FH92: If persisted responses are available, use them as the
        // canonical model-answer source. Events are only used for synthesis.
        if (persistedResponses && persistedResponses.length > 0) {
            for (const r of persistedResponses) {
                eventResponses.push({
                    model_id: r.model_id,
                    display_name: r.display_name,
                    provider: r.provider,
                    content: r.content || "",
                    logo_url: r.metadata?.logo_url || undefined,
                    persona_type: r.metadata?.persona_type || undefined,
                    success: r.success,
                });
            }
        } else {
            // Fallback: derive from events (legacy path)
            for (const evt of events) {
                if (evt.type === "arena_response") {
                    const e = evt as any;
                    eventResponses.push({
                        model_id: e.model_id || "",
                        display_name: e.display_name || e.seat_name || "Model",
                        provider: e.provider || "",
                        content: e.content || e.text || "",
                        logo_url: e.logo_url,
                        persona_type: e.persona_type,
                        success: e.success !== false,
                    });
                }
            }
        }

        // Extract synthesis from events (always event-based)
        for (const evt of events) {
            if (evt.type === "arena_synthesis") {
                synthesisText = (evt as any).text || (evt as any).content || "";
            } else if (evt.type === "final" && !synthesisText) {
                synthesisText = (evt as any).text || "";
            }
        }

        // Fallback: if no arena events, try final_content from debate
        if (!synthesisText && debate.final_content) {
            synthesisText = debate.final_content;
        }

        // Fallback: try to extract model responses from top-level models or final_meta
        const fallbackModels = debate.models ?? debate.final_meta?.models;
        if (eventResponses.length === 0 && fallbackModels) {
            const seatMessages = events.filter((e: any) => e.type === "seat_message");
            for (const model of fallbackModels) {
                const matching = seatMessages.find((e: any) =>
                    (e as any).display_name === model.display_name ||
                    (e as any).seat_name === model.display_name
                );
                eventResponses.push({
                    model_id: model.model_id,
                    display_name: model.display_name,
                    provider: model.provider,
                    content: (matching as any)?.content || (matching as any)?.text || "",
                    logo_url: model.logo_url,
                    persona_type: model.persona_type,
                    success: model.success !== false,
                });
            }
        }

        return { modelResponses: eventResponses, synthesis: synthesisText };
    }, [events, debate, persistedResponses]);

    // P143: Canonical synthesis artifacts — one normalizer for public & private shapes
    const artifacts = useMemo(
        () => getArenaSynthesisArtifacts(debate, synthesis),
        [debate, synthesis],
    );

    const handleRetryAgent = async (personaName: string) => {
        const res = await fetchWithAuth(`/debates/${debate.id}/retry-agent`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ persona: personaName }),
        });
        if (!res.ok) {
            const errBody = await res.json().catch(() => ({}));
            throw new Error(errBody.detail || errBody.message || "Failed to retry agent");
        }
        if (onRefetch) {
            await onRefetch();
        } else {
            window.location.reload();
        }
    };

    // FH121: Correct loading formula — terminal Runs never show skeletons
    const showResponseSkeletons = !isTerminal && (responsesState === "idle" || responsesState === "loading");
    const isLoading = showResponseSkeletons && modelResponses.length === 0 && !artifacts.hasSynthesisOutput;
    const expectedModels =
        debate?.models_expected ||
        debate?.panel_config?.seats?.length ||
        debate?.final_meta?.models?.length ||
        (debate?.config as any)?.models?.length ||
        (debate as any)?.models?.length ||
        2;
    const [activeTab, setActiveTab] = useState<number>(0);
    const [mobileSegment, setMobileSegment] = useState<"perspectives" | "decision" | "verification">("perspectives");
    const { containerRef: cardContainerRef } = useCardKeyboardNav(modelResponses.length || expectedModels);

    const renderSlots = useMemo(() => {
        const arenaSlots = buildArenaSlots({
            panelSeats: debate?.panel_config?.seats,
            finalMetaModels: debate?.final_meta?.models,
            debateModels: debate?.models,
            persistedResponses: persistedResponses,
            streamingBuffers: streamingBuffers,
            fallbackModelIds: debate?.final_meta?.models?.map((m: any) => typeof m === "string" ? m : m.model_id),
        });

        // Track D: Render all slots in canonical order, preserving placeholders
        return arenaSlots.map(slot => ({
            type: slot.type === "persisted" ? "persisted" as const :
                   slot.type === "streaming" ? "stream" as const :
                   "skeleton" as const,
            resp: slot.persisted,
            streamBuf: slot.streaming,
            key: slot.key,
        }));
    }, [debate, persistedResponses, streamingBuffers]);

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
                                hasSynthesis={artifacts.hasSynthesisOutput}
                            />
                        </div>
                    ) : null}
                </div>
                {(debate.successful_count ?? debate.final_meta?.successful_count) != null && (
                    <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                            {debate.successful_count ?? debate.final_meta?.successful_count}/{debate.total_count ?? debate.final_meta?.total_count} models responded
                        </span>
                    </div>
                )}
                {debate.final_meta?.model_warnings?.length > 0 && (
                    <div className="mt-2 space-y-1">
                        {debate.final_meta.model_warnings.map((warn: any, i: number) => (
                            <p key={i} className="text-xs text-amber-600 dark:text-amber-400">
                                ⚠ {warn.display_name} ({warn.provider}): {warn.error}
                            </p>
                        ))}
                    </div>
                )}
            </div>

            {/* Mobile Segment Switcher — FH110 */}
            <div className="flex sm:hidden items-center gap-1 p-1 rounded-xl bg-muted/50 border border-border" role="tablist" aria-label="Run sections">
                {([
                    { key: "perspectives", label: "Perspectives", icon: Eye },
                    { key: "decision", label: "Decision", icon: MessageSquare },
                    { key: "verification", label: "Verification", icon: Shield },
                ] as const).map(({ key, label, icon: Icon }) => (
                    <button
                        key={key}
                        role="tab"
                        aria-selected={mobileSegment === key}
                        onClick={() => setMobileSegment(key)}
                        className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium transition-all ${
                            mobileSegment === key
                                ? "bg-card text-foreground shadow-sm"
                                : "text-muted-foreground hover:text-foreground"
                        }`}
                    >
                        <Icon className="h-3.5 w-3.5" />
                        {label}
                    </button>
                ))}
            </div>

            {/* FH121: Terminal empty/failed response states */}
            {isTerminal && responsesState === "empty" && modelResponses.length === 0 && (
                <div className="rounded-2xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 p-6 text-center">
                    <AlertTriangle className="h-8 w-8 text-amber-500 mx-auto mb-3" />
                    <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                        This Run reached a terminal state, but no persisted model responses were found.
                    </p>
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                        Run ID: {debate.id} · Status: {debate.status}
                    </p>
                    <button
                        onClick={() => onRefetch?.()}
                        className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-100 dark:bg-amber-800/50 text-xs font-medium text-amber-700 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-700/50 transition-colors"
                    >
                        <RefreshCw className="h-3 w-3" />
                        Retry response loading
                    </button>
                </div>
            )}

            {isTerminal && responsesState === "failed" && modelResponses.length === 0 && (
                <div className="rounded-2xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-6 text-center">
                    <AlertTriangle className="h-8 w-8 text-red-500 mx-auto mb-3" />
                    <p className="text-sm font-medium text-red-800 dark:text-red-200">
                        The Run loaded, but its stored model responses could not be retrieved.
                    </p>
                    {responsesError && (
                        <p className="text-xs text-red-600 dark:text-red-400 mt-1 font-mono">{responsesError}</p>
                    )}
                    <button
                        onClick={() => onRefetch?.()}
                        className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-100 dark:bg-red-800/50 text-xs font-medium text-red-700 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-700/50 transition-colors"
                    >
                        <RefreshCw className="h-3 w-3" />
                        Retry loading responses
                    </button>
                </div>
            )}

            {/* Model Response Cards */}
            <div>
                <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-2">
                    <Bot className="h-4 w-4" />
                    Model Responses
                </h2>

                {/* Mobile: full-width card with peek swipe */}
                <div className="flex sm:hidden flex-col gap-3">
                    {activeTab === 0 && modelResponses.length > 0 && (
                        <div className="flex items-center justify-center gap-1.5 text-[11px] font-medium text-muted-foreground animate-fade-in">
                            <span>Swipe to compare</span>
                            <ChevronRight className="h-3 w-3" />
                        </div>
                    )}
                    <div
                        className="flex overflow-x-auto snap-x snap-mandatory gap-3 px-4 pb-2 -mx-4"
                        style={{ scrollbarWidth: "none" }}
                        onScroll={(e) => {
                            const el = e.currentTarget;
                            const maxCards = Math.max(modelResponses.length || expectedModels, 1);
                            const cardWidth = el.scrollWidth / maxCards;
                            if (cardWidth > 0) {
                                const idx = Math.round(el.scrollLeft / cardWidth);
                                setActiveTab(idx);
                            }
                        }}
                    >
                        {renderSlots.map((slot, i) => {
                            if (slot.type === "skeleton") {
                                return (
                                    <div key={slot.key} className="snap-start shrink-0 w-[calc(100vw-4rem)] max-w-sm">
                                        <SkeletonCard index={i} />
                                    </div>
                                );
                            }

                            if (slot.type === "stream") {
                                const streamBuf = slot.streamBuf!;
                                return (
                                    <div key={slot.key} className="snap-start shrink-0 w-[calc(100vw-4rem)] max-w-sm">
                                        <StreamingModelCard
                                            displayName={streamBuf.displayName ?? "Model"}
                                            provider={streamBuf.provider}
                                            logoUrl={undefined}
                                            state={streamBuf.state}
                                            accumulatedText={streamBuf.accumulatedText}
                                            errorCode={streamBuf.errorCode}
                                            errorMessage={streamBuf.errorMessage}
                                            className="min-h-[350px]"
                                            onRetry={handleRetryAgent}
                                        />
                                    </div>
                                );
                            }

                            const resp = slot.resp!;
                            return (
                                <div key={slot.key} className="snap-start shrink-0 w-[calc(100vw-4rem)] max-w-sm">
                                    <ModelCard
                                        resp={resp}
                                        className="min-h-[350px]"
                                        onRetry={handleRetryAgent}
                                    />
                                </div>
                            );
                        })}
                        {/* Right-edge peek spacer */}
                        <div className="shrink-0 w-8" aria-hidden />
                    </div>
                    {/* Dot indicators */}
                    {(modelResponses.length || expectedModels) > 1 && (
                        <div className="flex justify-center gap-1.5">
                            {Array.from({ length: expectedModels }).map((_, i) => (
                                <div
                                    key={i}
                                    className={`h-1.5 rounded-full transition-all ${
                                        i === activeTab
                                            ? "w-4 bg-primary"
                                            : i < modelResponses.length
                                                ? "w-1.5 bg-primary/40"
                                                : "w-1.5 bg-muted-foreground/20"
                                    }`}
                                />
                            ))}
                        </div>
                    )}
                </div>

                {/* Desktop View: Render grid of all cards with keyboard navigation */}
                <div
                    ref={cardContainerRef}
                    className="hidden sm:grid grid-cols-1 md:grid-cols-2 gap-6"
                    role="group"
                    aria-label="Model responses (use arrow keys to navigate)"
                >
                    {renderSlots.map((slot, i) => {
                        if (slot.type === "skeleton") {
                            return <SkeletonCard key={slot.key} index={i} />;
                        }

                        if (slot.type === "stream") {
                            const streamBuf = slot.streamBuf!;
                            return (
                                <div key={slot.key} data-model-card tabIndex={0}>
                                    <StreamingModelCard
                                        displayName={streamBuf.displayName ?? "Model"}
                                        provider={streamBuf.provider}
                                        logoUrl={undefined}
                                        state={streamBuf.state}
                                        accumulatedText={streamBuf.accumulatedText}
                                        errorCode={streamBuf.errorCode}
                                        errorMessage={streamBuf.errorMessage}
                                        onRetry={handleRetryAgent}
                                    />
                                </div>
                            );
                        }

                        const resp = slot.resp!;
                        return (
                            <div key={slot.key} data-model-card tabIndex={0}>
                                <ModelCard
                                    resp={resp}
                                    onRetry={handleRetryAgent}
                                />
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Claims Divergence Analysis */}
            <DivergenceMeter 
                debateId={debate.id} 
                isCompleted={debate.status === "completed" || debate.status === "completed_budget"} 
                synthesisStatus={artifacts.synthesisStatus || debate.synthesis_status || debate.final_meta?.synthesis_status}
            />

            {/* Decision Report Section — live vs historical */}
            {presentation === "live" ? (
                (() => {
                    const hasReport = artifacts.hasStructuredReport && artifacts.synthesisReport;
                    const isSynthesizing = modelResponses.length > 0 && !artifacts.hasSynthesisOutput && !artifacts.hasStructuredReport;
                    const isSynthesisFailed = artifacts.synthesisStatus === "failed" ||
                        (debate.synthesis_success === false || debate.final_meta?.synthesis_success === false) ||
                        (artifacts.synthesisStatus === undefined && artifacts.synthesisText.startsWith("⚠️ Synthesis unavailable"));

                    return (
                        <div className="rounded-2xl border border-border bg-card/60 p-6 shadow-sm">
                            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4">
                                Decision Report
                            </h3>

                            {hasReport ? (
                                <DecisionReportView
                                    report={artifacts.synthesisReport}
                                    rawSynthesis={artifacts.synthesisText}
                                    variant="arena"
                                    synthesisStatus={artifacts.synthesisStatus || (isSynthesisFailed ? "failed" : "succeeded")}
                                    synthesisError={artifacts.synthesisError}
                                    fallbackModel={artifacts.fallbackModel}
                                    fallbackReason={artifacts.fallbackReason}
                                    fallbackResponse={artifacts.fallbackResponse}
                                    divergenceBreakdown={artifacts.divergenceBreakdown}
                                />
                            ) : isSynthesizing ? (
                                <div className="space-y-4">
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                        <div className="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                                        Synthesizing the final decision report…
                                    </div>
                                    {/* Structured skeleton */}
                                    <div className="space-y-3">
                                        <div className="h-20 bg-muted/50 rounded-lg animate-pulse" />
                                        <div className="h-8 w-24 bg-muted/50 rounded-lg animate-pulse" />
                                        <div className="space-y-2">
                                            <div className="h-4 bg-muted/50 rounded animate-pulse" />
                                            <div className="h-4 w-3/4 bg-muted/50 rounded animate-pulse" />
                                            <div className="h-4 w-1/2 bg-muted/50 rounded animate-pulse" />
                                        </div>
                                        <div className="grid grid-cols-2 gap-2">
                                            <div className="h-24 bg-muted/50 rounded-lg animate-pulse" />
                                            <div className="h-24 bg-muted/50 rounded-lg animate-pulse" />
                                        </div>
                                        <div className="space-y-2">
                                            <div className="h-4 bg-muted/50 rounded animate-pulse" />
                                            <div className="h-4 w-2/3 bg-muted/50 rounded animate-pulse" />
                                        </div>
                                    </div>
                                </div>
                            ) : artifacts.hasSynthesisOutput ? (
                                // Unstructured synthesis fallback — render directly without reveal
                                <SynthesisReveal
                                    synthesis={artifacts.synthesisText}
                                    modelResponses={modelResponses}
                                    isSynthesisFailed={isSynthesisFailed}
                                    debateId={debate.id}
                                    synthesisReport={artifacts.synthesisReport}
                                    synthesisStatus={artifacts.synthesisStatus}
                                    synthesisError={artifacts.synthesisError}
                                    fallbackModel={artifacts.fallbackModel}
                                    fallbackReason={artifacts.fallbackReason}
                                    fallbackResponse={artifacts.fallbackResponse}
                                    divergenceBreakdown={artifacts.divergenceBreakdown}
                                />
                            ) : (
                                // Waiting for responses — empty report placeholder
                                <div className="h-32 bg-muted/20 rounded-lg border border-dashed border-border flex items-center justify-center text-xs text-muted-foreground">
                                    Report will appear after model responses are collected
                                </div>
                            )}
                        </div>
                    );
                })()
            ) : (
                /* Historical: existing SynthesisReveal interaction */
                <>
                    {artifacts.hasSynthesisOutput && (() => {
                        const isSynthesisFailed = artifacts.synthesisStatus === "failed" ||
                            (debate.synthesis_success === false || debate.final_meta?.synthesis_success === false) ||
                            (artifacts.synthesisStatus === undefined && artifacts.synthesisText.startsWith("⚠️ Synthesis unavailable"));
                        return (
                            <SynthesisReveal
                                synthesis={artifacts.synthesisText}
                                modelResponses={modelResponses}
                                isSynthesisFailed={isSynthesisFailed}
                                debateId={debate.id}
                                synthesisReport={artifacts.synthesisReport}
                                synthesisStatus={artifacts.synthesisStatus}
                                synthesisError={artifacts.synthesisError}
                                fallbackModel={artifacts.fallbackModel}
                                fallbackReason={artifacts.fallbackReason}
                                fallbackResponse={artifacts.fallbackResponse}
                                divergenceBreakdown={artifacts.divergenceBreakdown}
                            />
                        );
                    })()}
                    {modelResponses.length > 0 && !artifacts.hasSynthesisOutput && !artifacts.hasStructuredReport && (
                        <SynthesisLoading successfulCount={modelResponses.filter(r => r.success).length} />
                    )}
                </>
            )}

            {!profile && debate.status === "completed" && (
                <PublicRunCTAFooter debateId={debate.id} />
            )}
        </div>
    );
}
