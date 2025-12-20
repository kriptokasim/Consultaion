/**
 * Patchset 76: Enhanced ConversationTimeline with delayed voting
 * 
 * Adds delayed vote CTA, feature flag gating, and animated transitions.
 */
"use client";

import { cn } from "@/lib/utils";
import { useMemo, useState, useCallback } from "react";
import { useDelayedVote } from "@/hooks/useDelayedVote";
import { VoteBar, VoteValue } from "@/components/voting/VoteBar";
import { VoteReasonSheet, VoteReasonType, ConfidenceLevel } from "@/components/voting/VoteReasonSheet";
import { AssistantBlock } from "./AssistantBlock";

interface ConversationTimelineProps {
    events: any[];
    activePersona?: string;
    truncated?: boolean;
    truncateReason?: string | null;
    /** Enable Conversation V2 features */
    enableV2?: boolean;
    /** Callback when vote is cast */
    onVote?: (data: {
        vote: VoteValue;
        reason?: VoteReasonType;
        confidence?: ConfidenceLevel
    }) => void;
}

export function ConversationTimeline({
    events,
    activePersona,
    truncated,
    truncateReason,
    enableV2 = false,
    onVote,
}: ConversationTimelineProps) {
    const [pendingVote, setPendingVote] = useState<VoteValue>(null);
    const [showReasonSheet, setShowReasonSheet] = useState(false);

    const { canShowVote, dwellTime } = useDelayedVote({
        dwellTimeMs: 5000,
        enabled: enableV2,
    });

    const { rounds, roundPhases } = useMemo(() => {
        const grouped: Record<number, any[]> = {};
        const phases: Record<number, string> = {};

        events.forEach((event) => {
            if (event.type === "round_started") {
                phases[event.round] = event.phase;
                return;
            }
            if (
                event.type !== "seat_message" &&
                event.type !== "conversation_summary" &&
                event.type !== "message"
            )
                return;
            const round = event.round ?? 0;
            if (!grouped[round]) grouped[round] = [];
            grouped[round].push(event);
        });
        return { rounds: grouped, roundPhases: phases };
    }, [events]);

    const getRoundLabel = (round: number, phase?: string) => {
        if (round === 0) return "Opening";
        if (phase === "synthesis") return "Final Synthesis";
        if (phase) return `Round ${round} – ${phase.replace(/_/g, " ")}`;
        return `Round ${round}`;
    };

    const handleVote = useCallback((vote: VoteValue) => {
        setPendingVote(vote);
        if (enableV2 && vote) {
            setShowReasonSheet(true);
        } else if (onVote) {
            onVote({ vote });
        }
    }, [enableV2, onVote]);

    const handleReasonSubmit = useCallback(
        (data: { reason?: VoteReasonType; confidence?: ConfidenceLevel }) => {
            onVote?.({
                vote: pendingVote,
                reason: data.reason,
                confidence: data.confidence,
            });
            setShowReasonSheet(false);
            setPendingVote(null);
        },
        [pendingVote, onVote]
    );

    const handleReasonClose = useCallback(() => {
        // Still submit the vote even if sheet is dismissed
        onVote?.({ vote: pendingVote });
        setShowReasonSheet(false);
        setPendingVote(null);
    }, [pendingVote, onVote]);

    return (
        <div className="space-y-8 pb-12">
            {Object.entries(rounds).map(([roundStr, messages]) => {
                const round = parseInt(roundStr);
                const phase = roundPhases[round];

                // Group assistant messages if V2 enabled
                const assistantMessages = enableV2
                    ? messages.filter(
                        (m: any) =>
                            m.type !== "conversation_summary" &&
                            m.seat_name !== "Scribe" &&
                            m.seat_name !== "Facilitator"
                    )
                    : [];

                return (
                    <div key={round} className="space-y-4">
                        <div className="flex items-center gap-4 py-2">
                            <div className="h-px flex-1 bg-slate-200" />
                            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                                {getRoundLabel(round, phase)}
                            </span>
                            <div className="h-px flex-1 bg-slate-200" />
                        </div>

                        {enableV2 && assistantMessages.length > 0 ? (
                            <AssistantBlock
                                messages={assistantMessages}
                                comparisonMode={true}
                                activePersona={activePersona}
                            />
                        ) : (
                            <div className="space-y-6">
                                {messages.map((msg: any, idx: number) => {
                                    const isScribe =
                                        msg.type === "conversation_summary" ||
                                        msg.seat_name === "Scribe";
                                    const isFacilitator = msg.seat_name === "Facilitator";

                                    return (
                                        <div
                                            key={idx}
                                            className={cn(
                                                "flex gap-4",
                                                isScribe || isFacilitator ? "justify-center" : ""
                                            )}
                                        >
                                            {!isScribe && !isFacilitator && (
                                                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-sm font-bold border border-indigo-200 shadow-sm">
                                                    {msg.seat_name?.[0] || "?"}
                                                </div>
                                            )}

                                            <div
                                                className={cn(
                                                    "p-4 rounded-2xl max-w-[85%] relative group transition-all",
                                                    isScribe
                                                        ? "bg-amber-50 border border-amber-100 text-amber-900 w-full text-center italic"
                                                        : isFacilitator
                                                            ? "bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-100 text-slate-800 w-full shadow-md"
                                                            : "bg-white border border-slate-200 shadow-sm text-slate-800 hover:shadow-md"
                                                )}
                                            >
                                                {!isScribe && !isFacilitator && (
                                                    <div className="flex items-center gap-2 mb-1.5">
                                                        <span className="text-xs font-bold text-slate-700">
                                                            {msg.seat_name}
                                                        </span>
                                                        <span className="inline-flex items-center rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
                                                            Delegate
                                                        </span>
                                                    </div>
                                                )}

                                                {isFacilitator && (
                                                    <div className="mb-2 flex justify-center">
                                                        <span className="inline-flex items-center rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700">
                                                            Final Synthesis
                                                        </span>
                                                    </div>
                                                )}

                                                <div className="prose prose-sm max-w-none whitespace-pre-wrap leading-relaxed">
                                                    {msg.content}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                );
            })}

            {truncated && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-center">
                    <p className="text-sm font-medium text-amber-800">
                        Conversation shortened due to{" "}
                        {truncateReason === "token_limit" ? "length limits" : "round limits"}.
                    </p>
                    <p className="text-xs text-amber-600 mt-1">
                        The Facilitator has synthesized the available discussion.
                    </p>
                </div>
            )}

            {/* V2: Delayed Vote CTA */}
            {enableV2 && (
                <div
                    className={cn(
                        "fixed bottom-6 left-1/2 -translate-x-1/2 z-40",
                        "transition-all duration-500",
                        canShowVote
                            ? "opacity-100 translate-y-0"
                            : "opacity-0 translate-y-4 pointer-events-none"
                    )}
                >
                    <div className="bg-white/95 backdrop-blur-sm border border-slate-200 rounded-full shadow-lg px-5 py-3 flex items-center gap-4">
                        <span className="text-sm text-slate-600">
                            Yanıtları okuduktan sonra oy verebilirsin
                        </span>
                        <VoteBar
                            value={pendingVote}
                            onVote={handleVote}
                            size="md"
                            aria-label="Vote on the conversation"
                        />
                    </div>
                </div>
            )}

            {/* Reason sheet */}
            <VoteReasonSheet
                open={showReasonSheet}
                onClose={handleReasonClose}
                onSubmit={handleReasonSubmit}
            />
        </div>
    );
}

export default ConversationTimeline;
