"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { Lock, Unlock, HelpCircle, CheckCircle, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface PredictionLockProps {
    debateId: string;
    candidates: string[];
    onLock: (prediction: { predicted_winner: string; confidence_score: number }) => Promise<void>;
    existingPrediction?: {
        predicted_winner: string;
        confidence_score: number;
        is_locked: boolean;
        is_correct?: boolean | null;
    } | null;
    disabled?: boolean;
}

export function PredictionLock({
    debateId,
    candidates,
    onLock,
    existingPrediction,
    disabled = false
}: PredictionLockProps) {
    const [selectedModel, setSelectedModel] = useState<string>(existingPrediction?.predicted_winner ?? "");
    const [confidence, setConfidence] = useState<number>(existingPrediction?.confidence_score ?? 0.5);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const isLocked = existingPrediction?.is_locked ?? false;
    const isCorrect = existingPrediction?.is_correct;

    const handleLock = async () => {
        if (!selectedModel) {
            setError("Please select a candidate to win.");
            return;
        }
        setError(null);
        setIsSubmitting(true);
        try {
            await onLock({
                predicted_winner: selectedModel,
                confidence_score: confidence
            });
        } catch (err: any) {
            setError(err?.message || "Failed to lock prediction.");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="relative overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-900/60 backdrop-blur-xl p-6 shadow-xl transition-all duration-300">
            {/* Background Glow */}
            <div className="absolute -right-20 -top-20 w-40 h-40 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />
            <div className="absolute -left-20 -bottom-20 w-40 h-40 rounded-full bg-violet-500/10 blur-3xl pointer-events-none" />

            <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                    {isLocked ? (
                        <span className="flex items-center justify-center w-8 h-8 rounded-full bg-amber-500/10 text-amber-500 animate-pulse">
                            <Lock className="w-4 h-4" />
                        </span>
                    ) : (
                        <span className="flex items-center justify-center w-8 h-8 rounded-full bg-indigo-500/10 text-indigo-500">
                            <Unlock className="w-4 h-4" />
                        </span>
                    )}
                    <div>
                        <h3 className="font-semibold text-slate-800 dark:text-slate-200">
                            Outcome Prediction
                        </h3>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                            {isLocked ? "Prediction locked for this run" : "Guess the winner before scores are calculated"}
                        </p>
                    </div>
                </div>

                {isLocked && isCorrect !== undefined && isCorrect !== null && (
                    <span className={cn(
                        "inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full",
                        isCorrect 
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" 
                            : "bg-rose-500/10 text-rose-600 dark:text-rose-400"
                    )}>
                        {isCorrect ? (
                            <>
                                <CheckCircle className="w-3 h-3" /> Correct Prediction
                            </>
                        ) : (
                            <>
                                <AlertCircle className="w-3 h-3" /> Incorrect Prediction
                            </>
                        )}
                    </span>
                )}
            </div>

            {error && (
                <div className="mb-4 text-xs font-medium text-rose-500 bg-rose-50 dark:bg-rose-950/20 border border-rose-100 dark:border-rose-900/30 p-3 rounded-lg flex items-center gap-2 animate-shake">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{error}</span>
                </div>
            )}

            {/* Candidate Selector */}
            <div className="space-y-3">
                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider block">
                    Choose Candidate Model
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {candidates.map((model) => {
                        const isSelected = selectedModel === model;
                        return (
                            <button
                                key={model}
                                type="button"
                                disabled={isLocked || disabled}
                                onClick={() => setSelectedModel(model)}
                                className={cn(
                                    "flex items-center justify-between p-4 rounded-xl border text-sm font-medium transition-all duration-200 text-left",
                                    isSelected
                                        ? "border-indigo-500 bg-indigo-500/5 text-indigo-900 dark:text-indigo-200 shadow-sm shadow-indigo-500/10"
                                        : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white/40 dark:bg-slate-900/40 text-slate-700 dark:text-slate-300",
                                    isLocked && isSelected && "opacity-100 border-amber-500 bg-amber-500/5 text-amber-900 dark:text-amber-200",
                                    isLocked && !isSelected && "opacity-50"
                                )}
                            >
                                <span className="truncate">{model}</span>
                                {isSelected && (
                                    <span className={cn(
                                        "w-2.5 h-2.5 rounded-full",
                                        isLocked ? "bg-amber-500" : "bg-indigo-500"
                                    )} />
                                )}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Confidence Slider */}
            <div className="mt-5 space-y-3">
                <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        Prediction Confidence
                        <span className="group relative cursor-pointer">
                            <HelpCircle className="w-3.5 h-3.5 text-slate-400 hover:text-slate-600" />
                            <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-48 p-2 rounded bg-slate-900 text-white text-[10px] leading-relaxed hidden group-hover:block z-10 shadow-lg">
                                How sure are you of this winner prediction?
                            </span>
                        </span>
                    </label>
                    <span className="text-sm font-bold text-indigo-600 dark:text-indigo-400">
                        {Math.round(confidence * 100)}%
                    </span>
                </div>
                <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    disabled={isLocked || disabled}
                    value={confidence}
                    onChange={(e) => setConfidence(parseFloat(e.target.value))}
                    className="w-full h-1.5 rounded-lg bg-slate-200 dark:bg-slate-800 accent-indigo-500 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                />
                <div className="flex justify-between text-[10px] text-slate-400 font-medium">
                    <span>Just Guessing</span>
                    <span>Uncertain</span>
                    <span>Highly Confident</span>
                </div>
            </div>

            {/* Lock Action */}
            {!isLocked && (
                <div className="mt-6 flex justify-end">
                    <Button
                        onClick={handleLock}
                        disabled={!selectedModel || disabled || isSubmitting}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20 px-5 py-2.5 rounded-xl font-semibold flex items-center gap-2 transition-transform active:scale-95 disabled:active:scale-100"
                    >
                        <Lock className="w-4 h-4" />
                        {isSubmitting ? "Locking..." : "Lock Prediction"}
                    </Button>
                </div>
            )}
        </div>
    );
}

export default PredictionLock;
