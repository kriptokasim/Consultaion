"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Sliders, Send, Network, Compass, CheckCircle2, ChevronRight, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { fetchWithAuth } from "@/lib/auth";

interface Node {
  id: string;
  raw_id: string;
  agent_id: string;
  round_index: number;
  type: string;
  claim: string;
  rebuts_target: string | null;
  position_drift?: {
    stubbornness?: number;
    cooperativeness?: number;
    text_justification?: string;
  };
}

export function ModeratorConsole({ debateId }: { debateId: string }) {
  const [round, setRound] = useState<number>(1);
  const [steeringText, setSteeringText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async () => {
    if (!steeringText.trim()) return;
    setIsSubmitting(true);
    setSuccess(false);
    try {
      const res = await fetchWithAuth(`/debates/${debateId}/moderate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          round_index: round,
          moderation_steering: steeringText,
        }),
      });
      if (res.ok) {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      }
    } catch (err) {
      console.error("Failed to post steering:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-primary/20 bg-card p-5 shadow-lg relative overflow-hidden">
      <div className="absolute top-0 right-0 h-24 w-24 bg-primary/5 rounded-full blur-xl -mr-6 -mt-6 pointer-events-none" />
      <div className="flex items-center gap-2 text-sm font-bold text-primary mb-3">
        <Sliders className="h-4 w-4" />
        Interactive Moderator steering
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Inject dynamic guidelines to steer agent behaviors for upcoming debate stages.
      </p>
      
      <div className="flex gap-2 mb-3">
        {[1, 2].map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => setRound(r)}
            className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold transition-all duration-200 border ${
              round === r
                ? "bg-primary text-primary-foreground border-primary shadow-sm"
                : "bg-muted text-muted-foreground border-border hover:bg-muted/80"
            }`}
          >
            Round {r} ({r === 1 ? "Drafts" : "Critiques"})
          </button>
        ))}
      </div>

      <textarea
        className="w-full h-24 bg-background border border-border rounded-xl px-3 py-2 text-xs focus:ring-2 focus:ring-primary focus:outline-none resize-none placeholder-muted-foreground/60 transition-all"
        placeholder={`Steer instructions for Round ${round} (e.g. "Focus strictly on technical implementation costs", "Challenge the security architecture assumptions")`}
        value={steeringText}
        onChange={(e) => setSteeringText(e.target.value)}
      />

      <div className="mt-3 flex items-center justify-between">
        {success ? (
          <span className="flex items-center gap-1 text-[11px] text-emerald-500 font-semibold animate-pulse">
            <CheckCircle2 className="h-3.5 w-3.5" /> Applied to pipeline
          </span>
        ) : (
          <span className="text-[10px] text-muted-foreground">Appended to system context</span>
        )}
        <Button
          size="sm"
          onClick={handleSubmit}
          disabled={isSubmitting || !steeringText.trim()}
          className="h-8 px-3 text-xs bg-primary hover:bg-primary/95 text-primary-foreground"
        >
          {isSubmitting ? "Sending..." : "Submit Guideline"}
          <Send className="ml-1.5 h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}

export function PositionDriftIndicator({ drift }: { drift?: Node["position_drift"] }) {
  if (!drift) return null;

  const stubborn = drift.stubbornness ?? 0.5;
  const coop = drift.cooperativeness ?? 0.5;

  return (
    <div className="mt-3 rounded-xl bg-accent-secondary/5 border border-border p-3">
      <div className="flex items-center justify-between text-xs font-bold text-foreground mb-2">
        <span className="flex items-center gap-1"><Compass className="h-3.5 w-3.5 text-primary" /> Stance Coordinates</span>
        <span className="text-[10px] text-muted-foreground">Drift Realignment</span>
      </div>

      <div className="space-y-2.5">
        <div>
          <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
            <span>Stubbornness</span>
            <span className="font-semibold text-foreground">{(stubborn * 100).toFixed(0)}%</span>
          </div>
          <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
            <div className="h-full bg-rose-500 rounded-full" style={{ width: `${stubborn * 100}%` }} />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
            <span>Cooperativeness</span>
            <span className="font-semibold text-foreground">{(coop * 100).toFixed(0)}%</span>
          </div>
          <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
            <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${coop * 100}%` }} />
          </div>
        </div>
      </div>

      {drift.text_justification && (
        <p className="mt-2 text-[10px] text-muted-foreground/90 italic leading-relaxed border-l-2 border-primary/20 pl-2">
          &ldquo;{drift.text_justification}&rdquo;
        </p>
      )}
    </div>
  );
}

export function ArgumentTree({ debateId }: { debateId: string }) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchTree = useCallback(async () => {
    try {
      const res = await fetchWithAuth(`/debates/${debateId}/argument-tree`);
      if (res.ok) {
        const data = await res.json();
        setNodes(data.nodes || []);
      }
    } catch (err) {
      console.error("Error loading argument tree:", err);
    } finally {
      setLoading(false);
    }
  }, [debateId]);

  useEffect(() => {
    fetchTree();
    // Poll for updates if debate is in progress
    const interval = setInterval(fetchTree, 10000);
    return () => clearInterval(interval);
  }, [debateId, fetchTree]);

  if (loading) {
    return (
      <div className="py-12 flex flex-col items-center justify-center text-muted-foreground gap-2">
        <div className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full" />
        <span className="text-xs">Resolving claim graph...</span>
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="py-12 flex flex-col items-center justify-center text-muted-foreground/60 gap-1.5 text-center">
        <Network className="h-8 w-8 stroke-[1.5]" />
        <p className="text-xs font-semibold">No logical arguments parsed yet</p>
        <p className="text-[10px] max-w-[200px]">Stance and claim graphs will appear as debate turns complete.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          <Network className="h-4 w-4 text-primary" /> Logical Claim Graph
        </h3>
        <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-semibold">
          {nodes.length} Logical Nodes
        </span>
      </div>

      <div className="space-y-3">
        {nodes.map((node) => {
          const isRebuttal = node.type === "rebuttal" || !!node.rebuts_target;
          return (
            <div
              key={node.id}
              className={`rounded-2xl border p-4 shadow-sm transition-all duration-300 ${
                isRebuttal
                  ? "border-rose-500/20 bg-rose-500/[0.02] hover:bg-rose-500/[0.04]"
                  : "border-emerald-500/20 bg-emerald-500/[0.02] hover:bg-emerald-500/[0.04]"
              }`}
            >
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="flex items-center gap-1 font-semibold text-foreground">
                  <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
                  {node.agent_id}
                  <span className="text-[10px] text-muted-foreground font-normal">
                    (Round {node.round_index})
                  </span>
                </span>
                <span
                  className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                    isRebuttal
                      ? "bg-rose-500/10 text-rose-600 dark:text-rose-400"
                      : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  }`}
                >
                  {node.type}
                </span>
              </div>

              <p className="text-xs text-foreground font-medium leading-relaxed">
                {node.claim}
              </p>

              {node.rebuts_target && (
                <div className="mt-2.5 flex items-center gap-1 text-[10px] text-rose-500 font-semibold bg-rose-500/5 py-1 px-2.5 rounded-lg border border-rose-500/10 w-fit">
                  <span>Rebuts:</span>
                  <span className="text-foreground/85 font-mono">{node.rebuts_target}</span>
                </div>
              )}

              {node.position_drift && (
                <PositionDriftIndicator drift={node.position_drift} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
