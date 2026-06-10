"use client";

import React, { useState, useEffect, useMemo } from "react";
import { Eye, Trophy, Sparkles, Check, CheckCircle2, ChevronRight, MessageSquare, AlertTriangle } from "lucide-react";
import { apiRequest } from "@/lib/apiClient";
import { SynthesisCard } from "./SynthesisCard";
import { DecisionReportView } from "@/components/report/DecisionReportView";
import type { ModelResponse } from "./ModelCard";

interface SynthesisRevealProps {
  synthesis: string;
  modelResponses: ModelResponse[];
  isSynthesisFailed: boolean;
  debateId: string;
  synthesisReport?: any;
}

export function SynthesisReveal({
  synthesis,
  modelResponses,
  isSynthesisFailed,
  debateId,
  synthesisReport,
}: SynthesisRevealProps) {
  const [revealed, setRevealed] = useState(false);
  const [prediction, setPrediction] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);

  // Build structured report from synthesis text or use the direct synthesisReport
  const report = useMemo(() => {
    if (synthesisReport && (synthesisReport.verdict || synthesisReport.executive_summary)) return synthesisReport;
    if (!synthesis || isSynthesisFailed) return null;
    // Parse the synthesis into a structured report using heuristic extraction
    return buildReportFromSynthesis(synthesis, modelResponses);
  }, [synthesis, modelResponses, isSynthesisFailed, synthesisReport]);

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
          path: `/users/me/participation`, // Or we can post to the general interaction endpoint if available
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
        <SynthesisCard
          synthesis={synthesis}
          modelResponses={modelResponses}
          isSynthesisFailed={isSynthesisFailed}
        />

        {/* Structured Decision Report */}
        {report && !isSynthesisFailed && (
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/50 p-6 shadow-sm">
            <DecisionReportView report={report} rawSynthesis={synthesis} />
          </div>
        )}

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
                <CheckCircle2 className="h-4.5 w-4.5" />
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

/**
 * Client-side heuristic report builder.
 * Extracts structured data from synthesis markdown text.
 */
function buildReportFromSynthesis(synthesis: string, modelResponses: ModelResponse[]) {
  if (!synthesis) return null;

  const lines = synthesis.split("\n");
  const sections: Record<string, string[]> = {};
  let currentKey = "intro";
  let currentLines: string[] = [];

  for (const line of lines) {
    const headerMatch = line.match(/^#{1,3}\s+(.*)/);
    if (headerMatch) {
      if (currentLines.length) sections[currentKey] = currentLines;
      currentKey = headerMatch[1].trim().toLowerCase();
      currentLines = [];
    } else {
      currentLines.push(line);
    }
  }
  if (currentLines.length) sections[currentKey] = currentLines;

  // Extract verdict
  let decisionType = "mixed";
  let confidence = 0.65;
  const lowerSynth = synthesis.toLowerCase();
  if (/\b(proceed|recommended|strong support|go ahead)\b/.test(lowerSynth)) decisionType = "proceed";
  else if (/\b(revise|modify|adjust|needs work)\b/.test(lowerSynth)) decisionType = "revise";
  else if (/\b(defer|delay|wait|postpone)\b/.test(lowerSynth)) decisionType = "defer";
  else if (/\b(reject|against|not recommended|avoid)\b/.test(lowerSynth)) decisionType = "reject";

  const confMatch = synthesis.match(/(\d{1,3})\s*%/);
  if (confMatch) confidence = Math.min(1, parseInt(confMatch[1]) / 100);

  // Extract summary
  const summaryKeys = ["summary", "executive summary", "overview", "conclusion"];
  let executiveSummary = "";
  for (const key of summaryKeys) {
    if (sections[key]) {
      executiveSummary = sections[key].join("\n").slice(0, 500);
      break;
    }
  }
  if (!executiveSummary) {
    const paragraphs = synthesis.split("\n\n").filter(p => p.trim() && !p.trim().startsWith("#"));
    executiveSummary = paragraphs[0]?.slice(0, 500) || synthesis.slice(0, 500);
  }

  // Extract findings
  const findings: Array<{ title: string; summary: string; importance: string }> = [];
  const findingKeys = ["findings", "key findings", "insights", "analysis", "results"];
  for (const key of findingKeys) {
    if (sections[key]) {
      const items = sections[key].join("\n").split(/\n(?:\d+[\.)]\s+|-\s+|\*\s+)/).filter(s => s.trim().length > 10);
      for (const item of items.slice(0, 6)) {
        const trimmed = item.trim();
        let importance = "medium";
        if (/\b(critical|essential|key|important)\b/i.test(trimmed)) importance = "high";
        else if (/\b(minor|low|secondary)\b/i.test(trimmed)) importance = "low";
        findings.push({ title: trimmed.slice(0, 80), summary: trimmed.slice(0, 300), importance });
      }
      break;
    }
  }

  // Build model positions from responses
  const modelPositions = modelResponses.filter(r => r.success).map(r => {
    const content = r.content || "";
    let stance = "supportive";
    if (/\b(disagree|however|but|concern|risk)\b/i.test(content)) stance = "concerned";
    else if (/\b(neutral|depends|mixed)\b/i.test(content)) stance = "neutral";
    return {
      model: r.display_name,
      stance,
      strongest_point: content.slice(0, 200) || "No response captured",
      concern: "See full response for details",
    };
  });

  // Extract risks
  const risks: Array<{ item: string; type: string; severity: string }> = [];
  const riskKeys = ["risks", "risks and assumptions", "concerns", "challenges"];
  for (const key of riskKeys) {
    if (sections[key]) {
      const items = sections[key].join("\n").split(/\n(?:\d+[\.)]\s+|-\s+|\*\s+)/).filter(s => s.trim().length > 10);
      for (const item of items.slice(0, 8)) {
        const trimmed = item.trim();
        let severity = "medium";
        if (/\b(critical|severe|major)\b/i.test(trimmed)) severity = "critical";
        else if (/\b(high|significant)\b/i.test(trimmed)) severity = "high";
        else if (/\b(low|minor)\b/i.test(trimmed)) severity = "low";
        const type = /\b(assume|assuming|assumption)\b/i.test(trimmed) ? "assumption" : "risk";
        risks.push({ item: trimmed.slice(0, 200), type, severity });
      }
      break;
    }
  }

  // Extract next actions
  const nextActions: Array<{ action: string; priority: string }> = [];
  const actionKeys = ["next steps", "next actions", "actions", "recommendations", "what to do"];
  for (const key of actionKeys) {
    if (sections[key]) {
      const items = sections[key].join("\n").split(/\n(?:\d+[\.)]\s+|-\s+|\*\s+)/).filter(s => s.trim().length > 5);
      items.slice(0, 6).forEach((item, i) => {
        nextActions.push({
          action: item.trim().slice(0, 200),
          priority: i < 2 ? "now" : i < 4 ? "next" : "later",
        });
      });
      break;
    }
  }

  return {
    title: "Decision Report",
    executive_summary: executiveSummary,
    verdict: {
      recommendation: executiveSummary.slice(0, 300),
      confidence,
      decision_type: decisionType,
      rationale: executiveSummary.slice(0, 500),
    },
    key_findings: findings,
    model_positions: modelPositions,
    risks_and_assumptions: risks,
    next_actions: nextActions,
    caveats: [],
  };
}
