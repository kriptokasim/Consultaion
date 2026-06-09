"use client";

import React, { useState, useEffect, useRef } from "react";
import { CheckCircle2, AlertTriangle, ThumbsUp, Sparkles, Loader2, Check, Clock } from "lucide-react";
import { apiRequest } from "@/lib/apiClient";
import { useToast } from "@/components/ui/toast";
import { getColors } from "./ModelCard";
import { getWithExpiry, setWithExpiry, TTL } from "@/lib/localStorageTTL";

interface Claim {
  claim: string;
  models?: string[]; // for consensus
  model?: string;    // for contested
}

interface DivergenceReport {
  id: string;
  debate_id: string;
  divergence_score: number;
  consensus_claims: { claims: Claim[] };
  contested_claims: { claims: Claim[] };
  ready: boolean;
}

interface DivergenceMeterProps {
  debateId: string;
  isCompleted: boolean;
}

const POLL_INTERVALS = [2000, 3000, 4500, 6750, 10000, 15000, 15000, 15000, 15000, 15000];
const MAX_POLLS = POLL_INTERVALS.length;

export function DivergenceMeter({ debateId, isCompleted }: DivergenceMeterProps) {
  const [report, setReport] = useState<DivergenceReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [votedClaim, setVotedClaim] = useState<string | null>(null);
  const [votingFor, setVotingFor] = useState<string | null>(null);
  const [displayScore, setDisplayScore] = useState(50);
  const [pollCount, setPollCount] = useState(0);
  const [isPolling, setIsPolling] = useState(false);
  const { pushToast } = useToast();
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prefersReducedMotion = useRef(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      prefersReducedMotion.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }
  }, []);

  // Animate score from 50% to actual score on mount
  useEffect(() => {
    if (report?.divergence_score !== undefined) {
      const target = report.divergence_score * 100;
      const duration = prefersReducedMotion.current ? 0 : 1000;
      if (duration === 0) {
        setDisplayScore(target);
        return;
      }
      const startTime = Date.now();
      const startValue = 50;
      const animate = () => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Spring-like easing (ease-out cubic)
        const eased = 1 - Math.pow(1 - progress, 3);
        setDisplayScore(startValue + (target - startValue) * eased);
        if (progress < 1) {
          requestAnimationFrame(animate);
        }
      };
      requestAnimationFrame(animate);
    }
  }, [report?.divergence_score]);

  const fetchReport = async () => {
    try {
      const data = await apiRequest<DivergenceReport>({
        path: `/arena/${debateId}/divergence`,
        method: "GET",
      });
      setReport(data);
      if (!data.ready && pollCount < MAX_POLLS) {
        setIsPolling(true);
        const nextInterval = POLL_INTERVALS[pollCount] || 15000;
        pollTimerRef.current = setTimeout(() => {
          setPollCount((c) => c + 1);
        }, nextInterval);
      } else {
        setIsPolling(false);
      }
      return data;
    } catch (err: any) {
      console.error("Failed to load divergence report:", err);
      setError("Unable to compute claims divergence at this time.");
      setIsPolling(false);
      return null;
    }
  };

  useEffect(() => {
    if (!isCompleted) return;
    setLoading(true);
    fetchReport().finally(() => setLoading(false));

    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [debateId, isCompleted, pollCount]);

  // Load voted state from localStorage for UX stickiness
  useEffect(() => {
    const stored = getWithExpiry<string>(`voted_claim_${debateId}`);
    if (stored) setVotedClaim(stored);
  }, [debateId]);

  const handleVote = async (claimText: string, modelName: string, isConsensus: boolean) => {
    if (votedClaim || votingFor) return;
    setVotingFor(claimText);
    try {
      await apiRequest({
        path: `/arena/${debateId}/user-vote`,
        method: "POST",
        body: {
          claim_text: claimText,
          model_name: modelName,
          is_consensus: isConsensus,
        },
      });
      setVotedClaim(claimText);
      setWithExpiry(`voted_claim_${debateId}`, claimText, TTL.VOTE_STATE);
    } catch (err: any) {
      console.error("Failed to submit claim vote:", err);
      if (err?.body?.detail?.includes("already voted")) {
        setVotedClaim(claimText);
        setWithExpiry(`voted_claim_${debateId}`, claimText, TTL.VOTE_STATE);
      } else {
        pushToast({
          title: "Couldn\u2019t cast vote",
          description: err?.body?.detail || "An error occurred while casting your vote. Please try again.",
          variant: "error",
        });
      }
    } finally {
      setVotingFor(null);
    }
  };

  if (!isCompleted) {
    return (
      <div className="rounded-2xl border border-dashed border-primary/20 bg-card/40 p-6 flex flex-col items-center justify-center text-center gap-3">
        <Sparkles className="h-6 w-6 text-muted-foreground animate-pulse" />
        <div>
          <p className="text-sm font-semibold text-foreground">Divergence Analysis Pending</p>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm">
            Once the debate finishes, we will extract claims and visualize areas of consensus and disagreement.
          </p>
        </div>
      </div>
    );
  }

  if (loading && !report) {
    return (
      <div className="rounded-2xl border border-border bg-card/50 p-8 flex flex-col items-center justify-center text-center gap-4">
        <Loader2 className="h-8 w-8 text-primary animate-spin" />
        <p className="text-sm font-medium text-muted-foreground animate-pulse">
          Analyzing model disagreement&hellip;
        </p>
        <p className="text-xs text-muted-foreground/70">
          Extracting consensus and contested claims.
        </p>
      </div>
    );
  }

  // Polling state: not ready yet
  if (report && !report.ready) {
    return (
      <div className="rounded-2xl border border-border bg-card/50 p-8 flex flex-col items-center justify-center text-center gap-4">
        <Clock className="h-8 w-8 text-amber-500 animate-pulse" />
        <p className="text-sm font-medium text-muted-foreground">
          Analyzing model disagreement&hellip;
        </p>
        <p className="text-xs text-muted-foreground/70">
          Extracting consensus and contested claims.
        </p>
        {pollCount >= 5 && (
          <p className="text-xs text-muted-foreground/50 italic">
            Taking longer than expected. Analysis is still processing.
          </p>
        )}
      </div>
    );
  }

  if (error || !report || !report.ready) {
    return null;
  }

  const { divergence_score, consensus_claims, contested_claims } = report;
  const scorePercent = Math.round(divergence_score * 100);

  // Determine label and color scheme based on divergence score
  let scoreLabel = "Balanced Deliberation";
  let scoreDescription = "Moderate level of unique claims and shared consensus points.";
  let badgeColor = "bg-amber-500/10 text-amber-500 border-amber-500/20";
  
  if (divergence_score < 0.3) {
    scoreLabel = "Strong Consensus";
    scoreDescription = "Models strongly aligned, sharing many key claims with minimal disagreement.";
    badgeColor = "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
  } else if (divergence_score > 0.7) {
    scoreLabel = "Stark Disagreement";
    scoreDescription = "Highly contested topic. Almost all models have proposed unique, divergent points.";
    badgeColor = "bg-rose-500/10 text-rose-500 border-rose-500/20";
  }

  return (
    <div className="rounded-2xl border border-border bg-gradient-to-b from-card via-card to-primary/5 p-6 shadow-md">
      {/* Title */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Claims Divergence Meter
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Analyzing consensus and divergence of key claims across all candidate responses.
          </p>
        </div>
        <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold border ${badgeColor}`}>
          {scoreLabel}
        </span>
      </div>

      {/* Slider / Bar Visualization */}
      <div className="space-y-3 mb-8">
        <div className="flex justify-between text-xs font-semibold text-muted-foreground px-1">
          <span>0% CONSENSUS</span>
          <span className="text-foreground text-sm font-bold">{scorePercent}% DIVIDED</span>
          <span>100% CONTESTED</span>
        </div>
        
        {/* Horizontal Track */}
        <div className="relative h-4 w-full rounded-full bg-muted overflow-hidden border border-border shadow-inner">
          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-r from-emerald-500 via-amber-500 to-rose-500 opacity-80" />
          {/* Slider line indicating position — animated */}
          <div 
            className="absolute top-0 bottom-0 w-2.5 bg-foreground border border-background shadow-lg"
            style={{
              left: `calc(${displayScore}% - 5px)`,
              transition: prefersReducedMotion.current ? "none" : "left 1s cubic-bezier(0.33, 1, 0.68, 1)",
            }}
          />
        </div>

        <p className="text-xs text-muted-foreground text-center italic mt-1.5">
          {scoreDescription}
        </p>
      </div>

      {/* Claims Lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-4 border-t border-border/60">
        
        {/* Consensus / Agreement */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-emerald-500">
            <CheckCircle2 className="h-5 w-5" />
            <h3 className="text-sm font-bold uppercase tracking-wider">Consensus Claims</h3>
          </div>
          
          {consensus_claims.claims.length === 0 ? (
            <p className="text-xs text-muted-foreground italic bg-muted/20 rounded-xl p-4 border border-dashed border-border">
              No overlapping claims detected. The models have entirely disjoint viewpoints.
            </p>
          ) : (
            <div className="space-y-3">
              {consensus_claims.claims.map((item, idx) => {
                const isSelected = votedClaim === item.claim;
                const isAnySelected = votedClaim !== null;
                const isVotingThis = votingFor === item.claim;
                
                return (
                  <div 
                    key={idx} 
                    className={`group relative flex flex-col justify-between gap-3 p-4 rounded-xl border transition-all ${
                      isSelected
                        ? "border-emerald-500 bg-emerald-500/5 shadow-sm shadow-emerald-500/10"
                        : "border-border bg-card/50 hover:bg-card hover:shadow-sm"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm text-foreground/90 leading-relaxed font-medium">
                        {item.claim}
                      </p>
                      
                      {/* Vote Button */}
                      <button
                        onClick={() => handleVote(item.claim, item.models?.[0] || "Model", true)}
                        disabled={isAnySelected || isVotingThis}
                        className={`shrink-0 flex items-center justify-center h-8 px-3 rounded-lg text-xs font-semibold border transition-all ${
                          isSelected
                            ? "bg-emerald-500 text-white border-emerald-500"
                            : isAnySelected
                            ? "opacity-40 cursor-not-allowed bg-muted text-muted-foreground border-border"
                            : "bg-emerald-500/10 hover:bg-emerald-500 hover:text-white border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
                        }`}
                        title={isSelected ? "You voted for this claim" : "Upvote this consensus point"}
                      >
                        {isVotingThis ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : isSelected ? (
                          <Check className="h-3.5 w-3.5" />
                        ) : (
                          <span className="flex items-center gap-1">
                            <ThumbsUp className="h-3 w-3" /> Agree
                          </span>
                        )}
                      </button>
                    </div>

                    {/* Model identity pills */}
                    <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-border/40">
                      <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wide mr-1">
                        Supported by:
                      </span>
                      {item.models?.map((model) => {
                        const colors = getColors(model);
                        return (
                          <span 
                            key={model}
                            className={`inline-flex items-center gap-1 text-[10px] font-semibold rounded-full px-2 py-0.5 border ${colors.border} ${colors.bg} ${colors.text}`}
                          >
                            <span className={`w-1.5 h-1.5 rounded-full ${colors.accent}`} />
                            {model}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Contested / Disagreements */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-rose-500">
            <AlertTriangle className="h-5 w-5" />
            <h3 className="text-sm font-bold uppercase tracking-wider">Contested Claims</h3>
          </div>

          {contested_claims.claims.length === 0 ? (
            <p className="text-xs text-muted-foreground italic bg-muted/20 rounded-xl p-4 border border-dashed border-border">
              No contested claims. The models reached complete agreement.
            </p>
          ) : (
            <div className="space-y-3">
              {contested_claims.claims.map((item, idx) => {
                const isSelected = votedClaim === item.claim;
                const isAnySelected = votedClaim !== null;
                const isVotingThis = votingFor === item.claim;
                
                return (
                  <div 
                    key={idx} 
                    className={`group relative flex flex-col justify-between gap-3 p-4 rounded-xl border transition-all ${
                      isSelected
                        ? "border-rose-500 bg-rose-500/5 shadow-sm shadow-rose-500/10"
                        : "border-border bg-card/50 hover:bg-card hover:shadow-sm"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm text-foreground/90 leading-relaxed font-medium">
                        {item.claim}
                      </p>

                      {/* Vote Button */}
                      <button
                        onClick={() => handleVote(item.claim, item.model || "Model", false)}
                        disabled={isAnySelected || isVotingThis}
                        className={`shrink-0 flex items-center justify-center h-8 px-3 rounded-lg text-xs font-semibold border transition-all ${
                          isSelected
                            ? "bg-rose-500 text-white border-rose-500"
                            : isAnySelected
                            ? "opacity-40 cursor-not-allowed bg-muted text-muted-foreground border-border"
                            : "bg-rose-500/10 hover:bg-rose-500 hover:text-white border-rose-500/30 text-rose-600 dark:text-rose-400"
                        }`}
                        title={isSelected ? "You voted for this claim" : "Upvote this unique claim"}
                      >
                        {isVotingThis ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : isSelected ? (
                          <Check className="h-3.5 w-3.5" />
                        ) : (
                          <span className="flex items-center gap-1">
                            <ThumbsUp className="h-3 w-3" /> Agree
                          </span>
                        )}
                      </button>
                    </div>

                    {/* Model identity pill */}
                    <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-border/40">
                      <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wide mr-1">
                        Proposed by:
                      </span>
                      {(() => {
                        const colors = getColors(item.model);
                        return (
                          <span className={`inline-flex items-center gap-1 text-[10px] font-semibold rounded-full px-2 py-0.5 border ${colors.border} ${colors.bg} ${colors.text}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${colors.accent}`} />
                            {item.model}
                          </span>
                        );
                      })()}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
