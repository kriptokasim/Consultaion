"use client";

import React from "react";
import { Award, ShieldAlert, Sparkles, MessageCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface VoteReasonCardProps {
    voteReasons: {
        winner_highlights: string[];
        dissenter_highlights: string[];
    } | null;
    className?: string;
}

export function VoteReasonCard({ voteReasons, className }: VoteReasonCardProps) {
    if (!voteReasons) return null;

    const { winner_highlights = [], dissenter_highlights = [] } = voteReasons;

    return (
        <div className={cn("grid grid-cols-1 md:grid-cols-2 gap-5", className)}>
            {/* Winner Highlights */}
            <div className="relative overflow-hidden rounded-2xl border border-emerald-100 dark:border-emerald-950/30 bg-gradient-to-br from-white to-emerald-50/20 dark:from-slate-900 dark:to-emerald-950/5 p-5 shadow-md transition-all duration-300">
                <div className="absolute right-0 top-0 w-24 h-24 bg-emerald-500/5 rounded-bl-full pointer-events-none" />
                <div className="flex items-center gap-2 mb-4">
                    <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-emerald-500/10 text-emerald-500">
                        <Award className="w-4 h-4" />
                    </span>
                    <h4 className="font-semibold text-slate-800 dark:text-slate-200 text-sm">
                        Winner Keys to Success
                    </h4>
                </div>

                {winner_highlights.length > 0 ? (
                    <ul className="space-y-3">
                        {winner_highlights.map((reason, idx) => (
                            <li key={idx} className="flex gap-2.5 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                                <Sparkles className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                                <span>{reason}</span>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="text-xs text-slate-400 dark:text-slate-500 italic flex items-center gap-1.5">
                        <MessageCircle className="w-3.5 h-3.5" /> No winner highlights recorded.
                    </p>
                )}
            </div>

            {/* Dissenter Drawbacks */}
            <div className="relative overflow-hidden rounded-2xl border border-rose-100 dark:border-rose-950/30 bg-gradient-to-br from-white to-rose-50/20 dark:from-slate-900 dark:to-rose-950/5 p-5 shadow-md transition-all duration-300">
                <div className="absolute right-0 top-0 w-24 h-24 bg-rose-500/5 rounded-bl-full pointer-events-none" />
                <div className="flex items-center gap-2 mb-4">
                    <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-rose-500/10 text-rose-500">
                        <ShieldAlert className="w-4 h-4" />
                    </span>
                    <h4 className="font-semibold text-slate-800 dark:text-slate-200 text-sm">
                        Dissenters Critique & Limits
                    </h4>
                </div>

                {dissenter_highlights.length > 0 ? (
                    <ul className="space-y-3">
                        {dissenter_highlights.map((reason, idx) => (
                            <li key={idx} className="flex gap-2.5 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                                <ShieldAlert className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                                <span>{reason}</span>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="text-xs text-slate-400 dark:text-slate-500 italic flex items-center gap-1.5">
                        <MessageCircle className="w-3.5 h-3.5" /> No dissenter reasons recorded.
                    </p>
                )}
            </div>
        </div>
    );
}

export default VoteReasonCard;
