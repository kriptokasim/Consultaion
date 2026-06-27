"use client";

import React, { useState, useEffect } from "react";
import { Eye, Trophy, ChevronRight, MessageSquare } from "lucide-react";
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
    return (
      <div className="space-y-6 animate-fade-in">
        {/* Canonical Decision Report View */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/50 p-6 shadow-sm animate-fade-in">
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
            Reveal Final Verdict
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
