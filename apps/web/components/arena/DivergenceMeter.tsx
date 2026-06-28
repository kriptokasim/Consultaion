"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { CheckCircle2, AlertTriangle, ThumbsUp, Sparkles, Loader2, Check, Clock } from "lucide-react";
import { apiRequest } from "@/lib/apiClient";
import { useToast } from "@/components/ui/toast";
import { getColors } from "./ModelCard";
import { getWithExpiry, setWithExpiry, TTL } from "@/lib/localStorageTTL";
import { DivergenceClaimList } from "./DivergenceClaimList";

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
  synthesisStatus?: string;
}

const POLL_INTERVALS = [2000, 3000, 4500, 6750, 10000, 15000, 15000, 15000, 15000, 15000];
const MAX_POLLS = 60; // 2 minutes max

export function DivergenceMeter({ debateId, isCompleted, synthesisStatus }: DivergenceMeterProps) {
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

  const fetchReport = useCallback(async () => {
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
        if (!data.ready && pollCount >= MAX_POLLS) {
          setError("Divergence analysis timed out. The run may still be processing — refresh to retry.");
        }
      }
      return data;
    } catch (err: any) {
      console.error("Failed to load divergence report:", err);
      setError("Unable to compute claims divergence at this time.");
      setIsPolling(false);
      return null;
    }
  }, [debateId, pollCount]);

  useEffect(() => {
    if (!isCompleted) return;
    setLoading(true);
    fetchReport().finally(() => setLoading(false));

    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [debateId, isCompleted, pollCount, fetchReport]);

  // Load voted state from localStorage for UX stickiness
  useEffect(() => {
    const stored = getWithExpiry<string>(`voted_claim_${debateId}`);
    if (stored) setVotedClaim(stored);
  }, [debateId]);

  const handleVote = async (claimText: string, claimId: string) => {
    if (votedClaim || votingFor) return;
    setVotingFor(claimText);
    try {
      await apiRequest({
        path: `/arena/${debateId}/user-vote`,
        method: "POST",
        body: {
          claim_id: claimId,
          claim_text: claimText,
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
    if (synthesisStatus === "failed") {
      return (
        <div className="rounded-2xl border border-rose-200 dark:border-rose-800 bg-rose-50/50 dark:bg-rose-950/20 p-4 text-sm text-rose-700 dark:text-rose-300">
          Divergence analysis unavailable — synthesis did not complete.
        </div>
      );
    }
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

  if (error) {
    return (
      <div className="rounded-2xl border border-rose-200 dark:border-rose-800 bg-rose-50/50 dark:bg-rose-950/20 p-4 text-sm text-rose-700 dark:text-rose-300">
        {error}
      </div>
    );
  }

  if (!report || !report.ready) {
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
        <DivergenceClaimList
          title="Consensus Claims"
          type="consensus"
          claims={consensus_claims.claims}
          emptyMessage="No overlapping claims detected. The models have entirely disjoint viewpoints."
          votedClaim={votedClaim}
          votingFor={votingFor}
          onVote={handleVote}
        />

        {/* Contested / Disagreements */}
        <DivergenceClaimList
          title="Contested Claims"
          type="contested"
          claims={contested_claims.claims}
          emptyMessage="No contested claims. The models reached complete agreement."
          votedClaim={votedClaim}
          votingFor={votingFor}
          onVote={handleVote}
        />

      </div>
    </div>
  );
}
