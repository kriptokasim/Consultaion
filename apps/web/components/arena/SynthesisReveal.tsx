"use client";

import React, { useState, useEffect } from "react";
import { Eye, Trophy, ChevronRight, MessageSquare, BookOpen } from "lucide-react";
import { apiRequest } from "@/lib/apiClient";
import { DecisionReportView } from "@/components/report/DecisionReportView";
import type { ModelResponse } from "./ModelCard";

interface SynthesisRevealProps {
  synthesis: string;
  modelResponses: ModelResponse[];
  isSynthesisFailed: boolean;
  debateId: string;
  synthesisReport?: any;
  synthesisStatus?: "pending" | "succeeded" | "failed" | "fallback";
  synthesisError?: string;
  fallbackModel?: string;
  fallbackReason?: string;
  fallbackResponse?: { model?: string; content?: string } | null;
  divergenceBreakdown?: any;
}

export function SynthesisReveal({
  synthesis,
  modelResponses,
  isSynthesisFailed,
  debateId,
  synthesisReport,
  synthesisStatus = "succeeded",
  synthesisError,
  fallbackModel,
  fallbackReason,
  fallbackResponse,
  divergenceBreakdown,
}: SynthesisRevealProps) {
  const [revealed, setRevealed] = useState(false);
  const [prediction, setPrediction] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);

  useEffect(() => {
    // Check if user previously revealed this synthesis
    const storedRevealed = localStorage.getItem(`synthesis_revealed_${debateId}`);
    if (storedRevealed === "true") {
      setRevealed(true);
    }
    const storedPrediction = localStorage.getItem(`synthesis_pred_${debateId}`);
    if (storedPrediction) {
      setPrediction(storedPrediction);
    }
    const storedFeedback = localStorage.getItem(`synthesis_feedback_${debateId}`);
    if (storedFeedback) {
      setFeedback(storedFeedback);
    }
  }, [debateId]);

  const handleReveal = async (selectedModel?: string) => {
    if (selectedModel) {
      setPrediction(selectedModel);
      localStorage.setItem(`synthesis_pred_${debateId}`, selectedModel);

      // Track interaction
      try {
        await apiRequest({
          path: `/users/me/participation`,
          method: "POST",
          body: {
            debate_id: debateId,
            interaction_type: "synthesis_prediction",
            details: { predicted_best_model: selectedModel },
          },
        }).catch(() => {
          // Fallback if generic endpoint isn't fully registered/auth is missing
        });
      } catch (err) {
        // ignore tracking failures
      }
    }
    setRevealed(true);
    localStorage.setItem(`synthesis_revealed_${debateId}`, "true");
  };

  const handleFeedbackSubmit = async (feedbackType: string) => {
    setFeedback(feedbackType);
    setSubmittingFeedback(true);
    localStorage.setItem(`synthesis_feedback_${debateId}`, feedbackType);

    try {
      // Post to participation / interaction tracking backend
      await apiRequest({
        path: `/users/me/participation`,
        method: "POST",
        body: {
          debate_id: debateId,
          interaction_type: "synthesis_feedback",
          details: { quality: feedbackType },
        },
      }).catch(() => {});
    } catch (e) {
      // ignore
    } finally {
      setSubmittingFeedback(false);
    }
  };

  if (revealed) {
    const verdict = synthesisReport?.verdict;
    const decisionType = verdict?.decision_type?.toLowerCase() || "mixed";
    const confidence = verdict?.confidence ? Math.round(verdict.confidence * 100) : null;

    const verdictConfig: Record<string, { label: string; bg: string; text: string; border: string }> = {
      proceed: {
        label: "PROCEED",
        bg: "bg-emerald-50 dark:bg-emerald-950/30",
        text: "text-emerald-700 dark:text-emerald-300",
        border: "border-emerald-200 dark:border-emerald-800",
      },
      reject: {
        label: "REJECT",
        bg: "bg-rose-50 dark:bg-rose-950/30",
        text: "text-rose-700 dark:text-rose-300",
        border: "border-rose-200 dark:border-rose-800",
      },
      investigate: {
        label: "INVESTIGATE",
        bg: "bg-amber-50 dark:bg-amber-950/30",
        text: "text-amber-700 dark:text-amber-300",
        border: "border-amber-200 dark:border-amber-800",
      },
      mixed: {
        label: "MIXED",
        bg: "bg-slate-50 dark:bg-slate-900/30",
        text: "text-slate-700 dark:text-slate-300",
        border: "border-slate-200 dark:border-slate-700",
      },
    };

    const vc = verdictConfig[decisionType] || verdictConfig.mixed;

    return (
      <div className="space-y-4 animate-fade-in">
        {/* ── Verdict Hero ── */}
        {verdict && verdict.decision_type && !isSynthesisFailed && (
          <div className={`rounded-2xl border-2 ${vc.border} ${vc.bg} px-6 py-5 flex flex-col sm:flex-row sm:items-center gap-4`}>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 flex-wrap">
                <span className={`inline-flex items-center rounded-full px-4 py-1.5 text-sm font-black tracking-widest uppercase ${vc.bg} ${vc.text} border ${vc.border}`}>
                  {vc.label}
                </span>
                {confidence !== null && (
                  <span className="text-xs font-semibold text-muted-foreground">
                    {confidence}% confidence
                  </span>
                )}
              </div>
              {verdict.rationale && (
                <p className="mt-2 text-sm text-foreground leading-relaxed">
                  {verdict.rationale}
                </p>
              )}
            </div>
            {/* Quality indicator */}
            {synthesisReport?.quality_meta?.completeness_score != null && (
              <div className="shrink-0 text-center">
                <div className="text-2xl font-black text-foreground">
                  {Math.round(synthesisReport.quality_meta.completeness_score * 100)}
                  <span className="text-xs font-normal text-muted-foreground">/100</span>
                </div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mt-0.5">
                  Report quality
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Full Report (collapsible) ── */}
        <details className="group rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/50 overflow-hidden">
          <summary className="flex cursor-pointer items-center justify-between px-6 py-4 text-sm font-semibold text-foreground hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors select-none list-none">
            <span className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-muted-foreground" />
              Full decision report
            </span>
            <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-90" />
          </summary>
          <div className="px-6 pb-6 pt-2 border-t border-slate-100 dark:border-slate-800">
            <DecisionReportView
              report={synthesisReport}
              rawSynthesis={synthesis}
              variant="arena"
              synthesisStatus={synthesisStatus || (isSynthesisFailed ? "failed" : "succeeded")}
              synthesisError={synthesisError}
              fallbackModel={fallbackModel}
              fallbackReason={fallbackReason}
              fallbackResponse={fallbackResponse}
              divergenceBreakdown={divergenceBreakdown}
            />
          </div>
        </details>



        {/* Post-Reveal Feedback Poll */}
        {!isSynthesisFailed && (
          <div className="rounded-2xl border border-border bg-card/60 p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <MessageSquare className="h-4.5 w-4.5 text-primary" />
              <h4 className="text-sm font-semibold text-foreground">
                How would you rate this synthesis?
              </h4>
            </div>

            {feedback ? (
              <div className="flex items-center gap-2 text-xs text-emerald-600 dark:text-emerald-400 bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-3">
                <ChevronRight className="h-4.5 w-4.5 rotate-90" />
                <span>Thank you for your feedback! You voted: <strong>{feedback}</strong></span>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {[
                  { label: "Perfectly Combined", value: "perfect" },
                  { label: "Missed Nuances", value: "missed_nuance" },
                  { label: "Biased Content", value: "biased" },
                ].map((item) => (
                  <button
                    key={item.value}
                    onClick={() => handleFeedbackSubmit(item.label)}
                    disabled={submittingFeedback}
                    className="px-3.5 py-1.5 rounded-xl border border-border bg-card text-xs font-medium text-foreground hover:bg-primary/5 hover:border-primary/30 transition-all"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // Pre-reveal cover card
  return (
    <div className="rounded-2xl border-2 border-dashed border-primary/35 bg-gradient-to-br from-primary/5 via-card to-primary/5 p-8 text-center shadow-lg relative overflow-hidden">
      {/* Decorative background glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-primary/10 rounded-full blur-3xl -z-10 pointer-events-none" />

      <div className="max-w-md mx-auto space-y-6">
        <div className="flex justify-center">
          <div className="rounded-2xl bg-primary/15 p-4 text-primary animate-bounce">
            <Trophy className="h-8 w-8" />
          </div>
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-bold text-foreground">Final Verdict Synthesized</h2>
          <p className="text-xs text-muted-foreground leading-relaxed">
            The independent evaluator has analyzed all candidate responses, weighed consensus points against contested issues, and compiled a single final verdict.
          </p>
        </div>

        {/* Prediction Poll */}
        {modelResponses.length > 0 && (
          <div className="bg-card/80 border border-border/80 rounded-xl p-4 space-y-3">
            <p className="text-xs font-semibold text-foreground">
              Who do you think made the most compelling case?
            </p>
            <div className="grid grid-cols-2 gap-2">
              {modelResponses
                .filter((r) => r.success)
                .map((r) => (
                  <button
                    key={r.model_id}
                    onClick={() => handleReveal(r.display_name)}
                    className="flex items-center justify-center gap-1.5 p-2 rounded-lg border border-border text-xs font-medium hover:bg-primary/5 hover:border-primary/30 transition-all text-muted-foreground hover:text-foreground text-center"
                  >
                    {r.display_name}
                  </button>
                ))}
            </div>
          </div>
        )}

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            onClick={() => handleReveal()}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-primary text-primary-foreground font-semibold hover:bg-primary/95 shadow-md shadow-primary/20 hover:shadow-lg transition-all text-sm"
          >
            <Eye className="h-4 w-4" />
            View Verdict & Report
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
