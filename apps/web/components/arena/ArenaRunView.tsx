"use client";

import React, { useMemo, useState } from "react";
import { Sparkles, Bot, CheckCircle2, Eye, MessageSquare, Shield, AlertTriangle, RefreshCw } from "lucide-react";
import type { DebateDetail, DebateEvent, PersistedModelResponse } from "@/lib/api/types";
import { ShareRunButton } from "@/components/debate/ShareRunButton";
import { ModelCard, StreamingModelCard, ModelLogo, SkeletonCard, getColors } from "./ModelCard";
import type { ModelResponse } from "./ModelCard";
import type { StreamingModelBuffer, ModelState } from "@/lib/streaming/types";
import type { ResponsesState, TimelineState } from "@/hooks/useRunWorkspace";
import { SynthesisCard, SynthesisLoading } from "./SynthesisCard";
import { PublicRunCTATop, PublicRunCTAFooter } from "./CTABanner";
import { DivergenceMeter } from "./DivergenceMeter";
import { SynthesisReveal } from "./SynthesisReveal";
import { fetchWithAuth } from "@/lib/auth";
import { useCardKeyboardNav } from "@/hooks/useCardKeyboardNav";

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
    profile?: any;
    onRefetch?: () => Promise<any> | void;
}

export default function ArenaRunView({ debate, events, responses: persistedResponses, streamingBuffers, isTerminal, responsesState, responsesError, timelineState, profile, onRefetch }: ArenaRunViewProps) {
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
                    persona_tagline: r.metadata?.persona_tagline || undefined,
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
                        persona_tagline: e.persona_tagline,
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

        // Fallback: try to extract model responses from final_meta
        if (eventResponses.length === 0 && debate.final_meta?.models) {
            const seatMessages = events.filter((e: any) => e.type === "seat_message");
            for (const model of debate.final_meta.models) {
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
                    persona_tagline: model.persona_tagline,
                    success: model.success !== false,
                });
            }
        }

        return { modelResponses: eventResponses, synthesis: synthesisText };
    }, [events, debate, persistedResponses]);

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
    const isLoading = showResponseSkeletons && modelResponses.length === 0 && !synthesis;
    const expectedModels = debate.final_meta?.models?.length || 4;
    const [activeTab, setActiveTab] = useState<number>(0);
    const [mobileSegment, setMobileSegment] = useState<"perspectives" | "decision" | "verification">("perspectives");
    const [touchStartX, setTouchStartX] = useState<number | null>(null);
    const { containerRef: cardContainerRef } = useCardKeyboardNav(modelResponses.length || expectedModels);

    const handleTouchStart = (e: React.TouchEvent) => {
        setTouchStartX(e.touches[0].clientX);
    };

    const handleTouchEnd = (e: React.TouchEvent) => {
        if (touchStartX === null) return;
        const touchEndX = e.changedTouches[0].clientX;
        const diffX = touchStartX - touchEndX;

        // Threshold of 50px for swipe gesture
        if (Math.abs(diffX) > 50) {
            if (diffX > 0) {
                // Swipe left -> next card (clamped, no circular wrap)
                setActiveTab((prev) => Math.min(prev + 1, modelResponses.length - 1));
            } else {
                // Swipe right -> previous card (clamped, no circular wrap)
                setActiveTab((prev) => Math.max(prev - 1, 0));
            }
        }
        setTouchStartX(null);
    };

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

                <div className="relative flex sm:hidden items-center w-full mb-4">
                    {/* Left gradient fade overlay */}
                    <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-background via-background/60 to-transparent pointer-events-none z-10" />

                    <div role="tablist" aria-label="Model responses" className="flex w-full overflow-x-auto gap-2 pb-2 px-6 custom-scrollbar">
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

                    {/* Right gradient fade overlay */}
                    <div className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-background via-background/60 to-transparent pointer-events-none z-10" />
                </div>

                {/* Mobile counter and progress dots */}
                <div className="flex sm:hidden items-center justify-between px-6 mb-3">
                    <span className="text-xs font-medium text-muted-foreground">
                        {activeTab + 1} of {modelResponses.length || expectedModels}
                    </span>
                    <div className="flex items-center gap-1.5">
                        {Array.from({ length: expectedModels }).map((_, i) => (
                            <button
                                key={i}
                                onClick={() => setActiveTab(i)}
                                className={`h-1.5 rounded-full transition-all duration-200 ${
                                    i === activeTab
                                        ? 'w-4 bg-primary'
                                        : i < modelResponses.length
                                            ? 'w-1.5 bg-primary/40'
                                            : 'w-1.5 bg-muted-foreground/20'
                                }`}
                                aria-label={`Go to model ${i + 1}`}
                            />
                        ))}
                    </div>
                </div>

                {/* Mobile View: Render only active card with swipe gesture handlers */}
                <div
                    role="tabpanel"
                    id={`model-panel-${modelResponses[activeTab]?.model_id || activeTab}`}
                    aria-labelledby={`model-tab-${modelResponses[activeTab]?.model_id || activeTab}`}
                    className="block sm:hidden outline-none"
                    onTouchStart={handleTouchStart}
                    onTouchEnd={handleTouchEnd}
                >
                    {(() => {
                        const resp = modelResponses[activeTab];
                        if (!resp) return <SkeletonCard index={activeTab} />;

                        const streamBuf = streamingBuffers?.get(`resp-${debate.id}-${resp.model_id}`);
                        if (streamBuf) {
                            return (
                                <StreamingModelCard
                                    displayName={resp.display_name}
                                    provider={resp.provider}
                                    logoUrl={resp.logo_url}
                                    personaTagline={resp.persona_tagline}
                                    state={streamBuf.state}
                                    accumulatedText={streamBuf.accumulatedText}
                                    errorCode={streamBuf.errorCode}
                                    errorMessage={streamBuf.errorMessage}
                                    className="min-h-[350px]"
                                    onRetry={handleRetryAgent}
                                />
                            );
                        }

                        return (
                            <ModelCard
                                resp={resp}
                                className="min-h-[350px]"
                                onRetry={handleRetryAgent}
                            />
                        );
                    })()}
                </div>

                {/* Desktop View: Render grid of all cards with keyboard navigation */}
                <div
                    ref={cardContainerRef}
                    className="hidden sm:grid grid-cols-2 xl:grid-cols-4 gap-4"
                    role="group"
                    aria-label="Model responses (use arrow keys to navigate)"
                >
                    {Array.from({ length: expectedModels }).map((_, i) => {
                        const resp = modelResponses[i];
                        if (!resp) {
                            return <SkeletonCard key={`skeleton-card-${i}`} index={i} />;
                        }

                        // FH103: Use StreamingModelCard when a streaming buffer exists for this model
                        const streamBuf = streamingBuffers?.get(`resp-${debate.id}-${resp.model_id}`);
                        if (streamBuf) {
                            return (
                                <div key={resp.model_id || i} data-model-card tabIndex={0}>
                                    <StreamingModelCard
                                        displayName={resp.display_name}
                                        provider={resp.provider}
                                        logoUrl={resp.logo_url}
                                        personaTagline={resp.persona_tagline}
                                        state={streamBuf.state}
                                        accumulatedText={streamBuf.accumulatedText}
                                        errorCode={streamBuf.errorCode}
                                        errorMessage={streamBuf.errorMessage}
                                        onRetry={handleRetryAgent}
                                    />
                                </div>
                            );
                        }

                        return (
                            <div key={resp.model_id || i} data-model-card tabIndex={0}>
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
            />

            {/* Synthesis / Final Verdict */}
            {synthesis && (() => {
                const isSynthesisFailed = debate.final_meta?.synthesis_status === "failed" || 
                                         debate.final_meta?.synthesis_success === false || 
                                         (debate.final_meta?.synthesis_status === undefined && synthesis.startsWith("⚠️ Synthesis unavailable"));
                return (
                    <SynthesisReveal 
                        synthesis={synthesis} 
                        modelResponses={modelResponses} 
                        isSynthesisFailed={isSynthesisFailed} 
                        debateId={debate.id}
                        synthesisReport={debate.synthesis_report || debate.final_meta?.synthesis_report}
                        synthesisStatus={debate.final_meta?.synthesis_status}
                        synthesisError={debate.final_meta?.synthesis_error}
                        fallbackModel={debate.final_meta?.fallback_model}
                        fallbackReason={debate.final_meta?.fallback_reason}
                        fallbackResponse={debate.final_meta?.fallback_response}
                        divergenceBreakdown={debate.final_meta?.divergence_breakdown}
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
