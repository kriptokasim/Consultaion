"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Eye, Trophy, Sparkles, HelpCircle, ArrowRight, Star } from "lucide-react";
import type { DebateDetail, DebateEvent } from "@/lib/api/types";
import { fetchWithAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import ParliamentRunView from "@/components/parliament/ParliamentRunView";
import DebateArena from "@/components/debate/DebateArena";
import { PredictionLock } from "./PredictionLock";
import { PredictionAggregate } from "./PredictionAggregate";
import { VoteReasonCard } from "./VoteReasonCard";
import { API_ORIGIN } from "@/lib/config/runtime";

interface VotingRunViewProps {
    debate: DebateDetail;
    events: DebateEvent[];
    isCompleted: boolean;
    resultsMembers?: any[];
    judgeVotes?: any[];
    scores?: any[];
    vote?: any;
    connectionStatus?: any;
}

export function VotingRunView({
    debate,
    events,
    isCompleted,
    resultsMembers = [],
    judgeVotes = [],
    scores = [],
    vote,
    connectionStatus = "idle"
}: VotingRunViewProps) {
    const [revealData, setRevealData] = useState<any>(null);
    const [isRevealed, setIsRevealed] = useState(false);
    const [loadingReveal, setLoadingReveal] = useState(false);

    const fetchReveal = useCallback(async () => {
        try {
            const res = await fetchWithAuth(`/voting/${debate.id}/reveal`);
            if (res.ok) {
                const data = await res.json();
                setRevealData(data);
                
                // Retrieve localStorage status for persistence
                const storedReveal = localStorage.getItem(`voting_revealed_${debate.id}`);
                if (storedReveal === "true") {
                    setIsRevealed(true);
                }
            }
        } catch (err) {
            console.error("Failed to retrieve prediction status:", err);
        }
    }, [debate.id]);

    useEffect(() => {
        fetchReveal();
    }, [fetchReveal]);

    // Handle prediction lock-in
    const handleLockPrediction = async (pred: { predicted_winner: string; confidence_score: number }) => {
        const res = await fetchWithAuth(`/voting/${debate.id}/predict`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                predicted_winner: pred.predicted_winner,
                confidence_score: pred.confidence_score,
                is_locked: true
            })
        });
        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData?.error?.message || "Failed to lock in prediction.");
        }
        await fetchReveal();
    };

    const handleRevealClick = () => {
        setIsRevealed(true);
        localStorage.setItem(`voting_revealed_${debate.id}`, "true");
    };

    // Collect candidates
    const candidates = useMemo(() => {
        if (debate.final_meta?.models) {
            return debate.final_meta.models.map((m: any) => m.display_name);
        }
        if ((debate.config as any)?.members) {
            return (debate.config as any).members.map((m: any) => m.name || m.model);
        }
        // Fallback extract from timeline events
        const names = new Set<string>();
        for (const evt of events) {
            const payload = (evt as any).payload || {};
            if (evt.type === "score") {
                names.add(payload.persona || (evt as any).persona);
            } else if (evt.type === "message" || evt.type === "seat_message") {
                const name = payload.seat_name || payload.actor || (evt as any).seat;
                if (name) names.add(name);
            }
        }
        return Array.from(names);
    }, [debate, events]);

    // Render active/running debate screen
    if (!isCompleted) {
        return (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 py-6">
                {/* Side lock panel */}
                <div className="lg:col-span-4 space-y-6">
                    <PredictionLock
                        debateId={debate.id}
                        candidates={candidates}
                        onLock={handleLockPrediction}
                        existingPrediction={revealData?.prediction}
                    />
                    {revealData?.prediction?.is_locked && (
                        <PredictionAggregate aggregates={revealData?.aggregates ?? []} />
                    )}
                </div>

                {/* Live Transcript Arena */}
                <div className="lg:col-span-8">
                    <DebateArena
                        debate={debate}
                        events={events as any}
                        connectionStatus={connectionStatus}
                    />
                </div>
            </div>
        );
    }

    // Render completed but not yet revealed results screen
    if (!isRevealed) {
        return (
            <div className="container max-w-3xl py-12">
                <div className="rounded-3xl border-2 border-dashed border-indigo-200 dark:border-indigo-950/60 bg-gradient-to-br from-indigo-50/10 via-card to-indigo-50/5 p-8 md:p-12 text-center shadow-xl relative overflow-hidden">
                    {/* Glow background */}
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl -z-10 pointer-events-none" />

                    <div className="max-w-md mx-auto space-y-6">
                        <div className="flex justify-center">
                            <div className="rounded-2xl bg-indigo-500/10 text-indigo-500 p-4 animate-bounce">
                                <Trophy className="h-8 w-8" />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <h2 className="text-2xl font-extrabold text-slate-800 dark:text-white tracking-tight">
                                Judge Votes Compiled!
                            </h2>
                            <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
                                The parliamentary debate is over and the scores are in. Reveal now to resolve your prediction and view community statistics.
                            </p>
                        </div>

                        {/* If they haven't predicted or predicted, show summary */}
                        {revealData?.prediction ? (
                            <div className="bg-indigo-50/40 dark:bg-indigo-950/10 border border-indigo-100/50 dark:border-indigo-950/40 rounded-2xl p-4">
                                <p className="text-xs text-slate-600 dark:text-slate-400">
                                    Your Locked Prediction:
                                </p>
                                <p className="text-base font-bold text-slate-800 dark:text-slate-200 mt-1 flex items-center justify-center gap-1.5">
                                    <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
                                    {revealData.prediction.predicted_winner}
                                    <span className="text-xs font-normal text-slate-400">
                                        ({Math.round(revealData.prediction.confidence_score * 100)}% confidence)
                                    </span>
                                </p>
                            </div>
                        ) : (
                            candidates.length > 0 && (
                                <div className="bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 space-y-3">
                                    <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                        Who do you think won the debate?
                                    </p>
                                    <div className="grid grid-cols-2 gap-2">
                                        {candidates.map((c: string) => (
                                            <button
                                                key={c}
                                                onClick={async () => {
                                                    try {
                                                        await handleLockPrediction({
                                                            predicted_winner: c,
                                                            confidence_score: 0.5
                                                        });
                                                        handleRevealClick();
                                                    } catch (e) {
                                                        // Fallback reveal direct
                                                        handleRevealClick();
                                                    }
                                                }}
                                                className="p-2 border border-slate-200 dark:border-slate-800 rounded-xl text-xs font-medium hover:bg-indigo-50 dark:hover:bg-indigo-950/20 hover:border-indigo-200 transition-all text-slate-600 dark:text-slate-400 hover:text-indigo-600"
                                            >
                                                {c}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )
                        )}

                        <div className="pt-2 flex justify-center">
                            <Button
                                onClick={handleRevealClick}
                                className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shadow-lg shadow-indigo-500/20 px-8 py-3 rounded-2xl flex items-center gap-2 transition-transform active:scale-95 text-sm"
                            >
                                <Eye className="w-4 h-4" />
                                Reveal Stance & Rationale
                                <ArrowRight className="w-4 h-4" />
                            </Button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // Render completed, fully revealed results screen
    return (
        <div className="space-y-8 py-6">
            {/* Top Row: Prediction Stance summary & Community Aggregates */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="md:col-span-1">
                    {revealData?.prediction ? (
                        <PredictionLock
                            debateId={debate.id}
                            candidates={candidates}
                            onLock={handleLockPrediction}
                            existingPrediction={revealData.prediction}
                            disabled={true}
                        />
                    ) : (
                        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/40 dark:bg-slate-900/40 p-6 backdrop-blur-md shadow-md flex flex-col justify-center items-center h-full text-center">
                            <HelpCircle className="w-8 h-8 text-slate-300 dark:text-slate-700 mb-2" />
                            <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                No Prediction Locked
                            </p>
                            <p className="text-[10px] text-slate-400 mt-1 max-w-[200px]">
                                You didn't submit a prediction lock before the debate was completed.
                            </p>
                        </div>
                    )}
                </div>

                <div className="md:col-span-2">
                    <PredictionAggregate aggregates={revealData?.aggregates ?? []} />
                </div>
            </div>

            {/* Judges reasons (Winner highlights vs Dissenter drawbacks) */}
            {revealData?.vote_reasons && (
                <div className="space-y-3">
                    <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 pl-1">
                        Judges' Rationale Summary
                    </h3>
                    <VoteReasonCard voteReasons={revealData.vote_reasons} />
                </div>
            )}

            {/* Traditional Parliament View below */}
            <div className="border-t border-slate-200 dark:border-slate-800 pt-8">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-4 pl-1">
                    Debate Outcome Details
                </h3>
                <ParliamentRunView
                    id={debate.id}
                    debate={debate}
                    scores={scores}
                    vote={vote}
                    events={events}
                    members={resultsMembers}
                    judgeVotes={judgeVotes}
                    threshold={0.5}
                    voteBasis="threshold"
                    apiBase={API_ORIGIN}
                />
            </div>
        </div>
    );
}

export default VotingRunView;
