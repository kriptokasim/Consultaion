"use client";

import React from "react";
import { Users, BarChart3, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import WilsonScoreBar from "./WilsonScoreBar";

export interface AggregateItem {
    candidate: string;
    count: number;
    percentage: number;
    mean_confidence: number;
    wilson_lower: number;
    wilson_upper: number;
}

export interface PredictionAggregateProps {
    aggregates: AggregateItem[];
    className?: string;
}

export function PredictionAggregate({ aggregates, className }: PredictionAggregateProps) {
    const totalPredictions = aggregates.reduce((sum, item) => sum + item.count, 0);

    return (
        <div className={cn("rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/40 dark:bg-slate-900/40 p-6 backdrop-blur-md shadow-md", className)}>
            <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                    <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-indigo-500/10 text-indigo-500">
                        <Users className="w-4 h-4" />
                    </span>
                    <div>
                        <h4 className="font-semibold text-slate-800 dark:text-slate-200 text-sm">
                            Community Consensus
                        </h4>
                        <p className="text-[10px] text-slate-400 dark:text-slate-500">
                            Live breakdown of all locked prediction ratios
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-300">
                    <BarChart3 className="w-3.5 h-3.5" />
                    <span>{totalPredictions} predictions</span>
                </div>
            </div>

            {totalPredictions > 0 ? (
                <div className="space-y-5">
                    {aggregates.map((item) => (
                        <div key={item.candidate} className="space-y-1">
                            <WilsonScoreBar
                                label={item.candidate}
                                percentage={item.percentage}
                                count={item.count}
                                total={totalPredictions}
                                wilsonLower={item.wilson_lower}
                                wilsonUpper={item.wilson_upper}
                            />
                            <div className="flex items-center gap-1 text-[10px] text-slate-500 dark:text-slate-400 mt-1 pl-1">
                                <TrendingUp className="w-3 h-3 text-indigo-500" />
                                <span>
                                    Average voter confidence: <strong>{Math.round(item.mean_confidence * 100)}%</strong>
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                    <Users className="w-8 h-8 text-slate-300 dark:text-slate-700 mb-2" />
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                        No predictions cast yet for this run.
                    </p>
                    <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1">
                        Be the first to predict!
                    </p>
                </div>
            )}
        </div>
    );
}

export default PredictionAggregate;
