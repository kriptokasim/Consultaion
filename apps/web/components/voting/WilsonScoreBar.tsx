"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface WilsonScoreBarProps {
    percentage: number; // e.g. 66.7
    wilsonLower: number; // e.g. 0.354
    wilsonUpper: number; // e.g. 0.879
    label: string;
    count: number;
    total: number;
    className?: string;
}

export function WilsonScoreBar({
    percentage,
    wilsonLower,
    wilsonUpper,
    label,
    count,
    total,
    className
}: WilsonScoreBarProps) {
    // Convert 0.0-1.0 interval bounds to percentage strings
    const lowerPercent = (wilsonLower * 100).toFixed(1);
    const upperPercent = (wilsonUpper * 100).toFixed(1);
    const intervalWidth = ((wilsonUpper - wilsonLower) * 100).toFixed(1);
    const intervalStart = (wilsonLower * 100).toFixed(1);

    return (
        <div className={cn("space-y-2 select-none", className)}>
            <div className="flex items-center justify-between text-xs font-semibold text-slate-700 dark:text-slate-300">
                <span className="truncate max-w-[200px]">{label}</span>
                <div className="flex items-center gap-1.5 shrink-0">
                    <span className="font-bold text-slate-900 dark:text-white">
                        {percentage}%
                    </span>
                    <span className="text-slate-400 dark:text-slate-500 font-normal">
                        ({count}/{total})
                    </span>
                </div>
            </div>

            {/* Premium Stat Track */}
            <div className="relative h-6 w-full bg-slate-100 dark:bg-slate-800/60 rounded-full overflow-hidden border border-slate-200/40 dark:border-slate-800/40">
                {/* 1. Shaded Wilson Interval Overlay */}
                <div
                    className="absolute top-0 bottom-0 bg-indigo-500/15 dark:bg-indigo-400/10 border-l border-r border-indigo-400/30 transition-all duration-500"
                    style={{
                        left: `${intervalStart}%`,
                        width: `${intervalWidth}%`,
                    }}
                />

                {/* 2. Mean Proportion Value Bar */}
                <div
                    className="absolute top-1 bottom-1 left-1 bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full transition-all duration-500"
                    style={{
                        width: `calc(${percentage}% - 8px)`,
                    }}
                />

                {/* 3. Invisible tooltip trigger */}
                <div className="absolute inset-0 group cursor-help">
                    <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2.5 w-60 p-2.5 rounded-xl bg-slate-900 text-white text-[10px] leading-relaxed hidden group-hover:block z-10 shadow-xl border border-slate-800">
                        <span className="font-bold block mb-1 text-slate-200">
                            95% Wilson Confidence Interval
                        </span>
                        Lower Bound: <strong className="text-indigo-400">{lowerPercent}%</strong>
                        <br />
                        Upper Bound: <strong className="text-indigo-400">{upperPercent}%</strong>
                        <br />
                        <span className="text-slate-400 mt-1 block">
                            Interval accounts for small sample sizes to avoid overconfidence.
                        </span>
                    </span>
                </div>
            </div>

            <div className="flex justify-between text-[9px] text-slate-400 font-medium px-1">
                <span>Stance Ratio: {percentage}%</span>
                <span>Confidence Range: [{lowerPercent}%, {upperPercent}%]</span>
            </div>
        </div>
    );
}

export default WilsonScoreBar;
