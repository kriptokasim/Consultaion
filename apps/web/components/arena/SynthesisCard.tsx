"use client";

import React from "react";
import { Trophy, AlertTriangle } from "lucide-react";
import type { ModelResponse } from "./ModelCard";
import { ModelLogo, getColors } from "./ModelCard";

import { sanitizeMarkdown } from "@/lib/sanitize";

interface SynthesisCardProps {
    synthesis: string;
    modelResponses: ModelResponse[];
    isSynthesisFailed?: boolean;
}

export function SynthesisCard({ synthesis, modelResponses, isSynthesisFailed = false }: SynthesisCardProps) {
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
                <div 
                    className="leading-relaxed text-foreground"
                    dangerouslySetInnerHTML={{ __html: sanitizeMarkdown(synthesis) }}
                />
            </div>

            {/* Model attribution chips */}
            {modelResponses.length > 0 && !isSynthesisFailed && (
                <div className="mt-6 border-t border-primary/10 pt-5">
                    <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
                        <div className="space-y-3">
                            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
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

                        <div className="md:max-w-xs rounded-xl bg-primary/5 p-4 border border-primary/10">
                            <p className="text-xs font-semibold uppercase tracking-wider text-primary mb-1">
                                Why this synthesis?
                            </p>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                                An independent, top-tier model evaluated the outputs above, fact-checked for disagreements, and combined the most accurate reasoning into this single artifact.
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

/* ─── Loading synthesis indicator ─── */
export function SynthesisLoading({ successfulCount }: { successfulCount: number }) {
    return (
        <div className="rounded-2xl border border-dashed border-primary/30 bg-primary/5 p-6 flex items-center gap-4">
            <div className="rounded-xl bg-primary/15 p-2.5 text-primary">
                <Trophy className="h-6 w-6 animate-pulse" />
            </div>
            <div>
                <p className="font-semibold text-foreground">Synthesizing Final Verdict…</p>
                <p className="text-sm text-muted-foreground">
                    Combining the strongest insights from {successfulCount} models
                </p>
            </div>
        </div>
    );
}
