"use client";

import React, { useState, useEffect } from "react";
import { 
  GitFork, HelpCircle, AlertTriangle, ArrowLeft, 
  Loader2, CheckCircle2, ChevronRight, MessageSquare, 
  Lightbulb, ShieldAlert, Sparkles, BookOpen, AlertCircle
} from "lucide-react";
import { apiRequest } from "@/lib/apiClient";
import { cn } from "@/lib/utils";

type ReasoningNode = {
  id: string;
  title: string;
  type: "fact" | "claim" | "uncertainty" | "conclusion";
  content: string;
};

type Branch = {
  id: string;
  parent_branch_id: string | null;
  assumption_text: string;
  nodes: ReasoningNode[];
  created_at: string;
};

type SessionState = {
  id: string;
  prompt: string;
  status: "running" | "completed";
  branches: Branch[];
  created_at: string;
};

const nodeTypeStyles = {
  fact: {
    bg: "bg-sky-500/10 border-sky-500/20 dark:bg-sky-950/20 dark:border-sky-850",
    text: "text-sky-700 dark:text-sky-400",
    label: "Fact / Axiom",
    icon: BookOpen
  },
  claim: {
    bg: "bg-purple-500/10 border-purple-500/20 dark:bg-purple-950/20 dark:border-purple-850",
    text: "text-purple-700 dark:text-purple-400",
    label: "Hypothesis",
    icon: Lightbulb
  },
  uncertainty: {
    bg: "bg-amber-500/10 border-amber-500/20 dark:bg-amber-950/20 dark:border-amber-850",
    text: "text-amber-700 dark:text-amber-400",
    label: "Uncertainty / Risk",
    icon: ShieldAlert
  },
  conclusion: {
    bg: "bg-emerald-500/10 border-emerald-500/20 dark:bg-emerald-950/20 dark:border-emerald-850",
    text: "text-emerald-700 dark:text-emerald-400",
    label: "Deduction / Verdict",
    icon: CheckCircle2
  }
};

export default function OracleWorkspace() {
  const [prompt, setPrompt] = useState("");
  const [session, setSession] = useState<SessionState | null>(null);
  const [activeBranchId, setActiveBranchId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedNodeId, setExpandedNodeId] = useState<string | null>(null);

  // Fork states
  const [forkNodeId, setForkNodeId] = useState<string | null>(null);
  const [forkAssumption, setForkAssumption] = useState("");
  const [forking, setForking] = useState(false);

  // Poll for status if running
  useEffect(() => {
    if (!session || session.status !== "running") return;

    const interval = setInterval(async () => {
      try {
        const data = await apiRequest<SessionState>({
          path: `/oracle/${session.id}`,
          method: "GET"
        });
        setSession(data);
        if (data.status === "completed") {
          // Default to root branch or new branch
          if (!activeBranchId && data.branches.length > 0) {
            // Find root branch (parent_branch_id is null)
            const root = data.branches.find(b => b.parent_branch_id === null);
            setActiveBranchId(root?.id || data.branches[0].id);
          } else if (data.branches.length > 0) {
            // If we were forking, select the newest branch
            const sorted = [...data.branches].sort((a, b) => 
              new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );
            setActiveBranchId(sorted[0].id);
          }
        }
      } catch (err: any) {
        console.error("Error polling oracle session:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [session, activeBranchId]);

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim().length < 5) {
      setError("Prompt must be at least 5 characters long.");
      return;
    }

    setLoading(true);
    setError(null);
    setExpandedNodeId(null);
    setForkNodeId(null);

    try {
      const data = await apiRequest<{ session_id: string; status: string }>({
        path: "/oracle",
        method: "POST",
        body: { prompt }
      });
      setSession({
        id: data.session_id,
        prompt,
        status: "running",
        branches: [],
        created_at: new Date().toISOString()
      });
      setActiveBranchId(null);
    } catch (err: any) {
      setError(err.message || "Failed to start reasoning session.");
    } finally {
      setLoading(false);
    }
  };

  const handleForkSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !activeBranchId || !forkNodeId || forkAssumption.trim().length < 3) return;

    setForking(true);
    setError(null);

    try {
      await apiRequest({
        path: `/oracle/${session.id}/fork`,
        method: "POST",
        body: {
          parent_branch_id: activeBranchId,
          fork_node_id: forkNodeId,
          assumption_text: forkAssumption
        }
      });
      setSession({
        ...session,
        status: "running"
      });
      setForkNodeId(null);
      setForkAssumption("");
    } catch (err: any) {
      setError(err.message || "Failed to submit fork counter-assumption.");
    } finally {
      setForking(false);
    }
  };

  const activeBranch = session?.branches.find(b => b.id === activeBranchId);

  if (session) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <button 
            onClick={() => {
              setSession(null);
              setActiveBranchId(null);
              setExpandedNodeId(null);
              setForkNodeId(null);
            }}
            className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Reset Oracle
          </button>
          <div className="flex items-center gap-2">
            <span className={cn(
              "px-3 py-1 text-xs font-bold rounded-full uppercase tracking-wider",
              session.status === "completed" 
                ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                : "bg-amber-500/10 text-amber-500 border border-amber-500/20 animate-pulse"
            )}>
              {session.status}
            </span>
          </div>
        </div>

        {session.status === "running" ? (
          <div className="flex flex-col items-center justify-center py-20 bg-card/40 rounded-2xl border border-border">
            <Loader2 className="h-10 w-10 text-primary animate-spin mb-4" />
            <h3 className="text-lg font-semibold text-foreground">Oracle is Reasoning...</h3>
            <p className="text-sm text-muted-foreground max-w-md text-center mt-2 px-6">
              Constructing a multi-layered logical chain of thought for your query. Counter-assumptions will fork this dynamically.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left Col: Branch Explorer */}
            <div className="lg:col-span-4 space-y-6">
              <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
                <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-4 flex items-center gap-2">
                  <GitFork className="h-4 w-4 text-primary" /> Reasoning Branches
                </h4>
                <div className="space-y-3">
                  {session.branches.map(b => (
                    <button
                      key={b.id}
                      onClick={() => {
                        setActiveBranchId(b.id);
                        setExpandedNodeId(null);
                        setForkNodeId(null);
                      }}
                      className={cn(
                        "w-full text-left p-4 rounded-xl border transition-all hover:bg-muted/10 flex items-start gap-3",
                        activeBranchId === b.id 
                          ? "bg-primary/5 border-primary text-foreground" 
                          : "bg-card border-border text-muted-foreground hover:text-foreground"
                      )}
                    >
                      <GitFork className="h-4 w-4 shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/60">
                          {b.parent_branch_id ? "Forked Branch" : "Root Branch"}
                        </p>
                        <p className="text-xs font-semibold mt-1 truncate max-w-[200px]">
                          {b.assumption_text}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
                <h4 className="text-xs font-bold text-accent-secondary uppercase tracking-wider mb-2">Original Inquiry</h4>
                <p className="text-xs text-foreground/80 font-mono bg-accent-secondary/5 rounded-xl p-3 border border-accent-secondary/10">
                  {session.prompt}
                </p>
              </div>
            </div>

            {/* Right Col: Visible Chain of Thought */}
            <div className="lg:col-span-8 space-y-6">
              {activeBranch ? (
                <div className="space-y-6 relative">
                  <div className="absolute left-[27px] top-6 bottom-6 w-[2px] bg-border dark:bg-stone-800" />
                  
                  {activeBranch.nodes.map((node, index) => {
                    const style = nodeTypeStyles[node.type] || { bg: "bg-muted", text: "text-foreground", label: node.type, icon: HelpCircle };
                    const Icon = style.icon;
                    const isExpanded = expandedNodeId === node.id;
                    const isForking = forkNodeId === node.id;

                    return (
                      <div key={node.id} className="relative pl-14 group">
                        {/* Timeline Icon Node */}
                        <div className={cn(
                          "absolute left-3 top-0 h-9 w-9 rounded-full border flex items-center justify-center transition-all bg-card",
                          isExpanded ? "ring-2 ring-primary/45 border-primary scale-110" : "border-border"
                        )}>
                          <Icon className={cn("h-4 w-4", style.text)} />
                        </div>

                        {/* Node Card */}
                        <div className={cn(
                          "rounded-2xl border p-4 bg-card shadow-sm hover:shadow transition-all cursor-pointer",
                          isExpanded ? "border-primary/40" : "border-border"
                        )}>
                          <div 
                            onClick={() => {
                              setExpandedNodeId(isExpanded ? null : node.id);
                              setForkNodeId(null);
                            }}
                            className="flex items-center justify-between"
                          >
                            <div>
                              <span className={cn(
                                "px-2 py-0.5 text-[9px] font-bold rounded-full uppercase tracking-wider border",
                                style.bg, style.text
                              )}>
                                {style.label}
                              </span>
                              <h5 className="font-bold text-foreground mt-2">{node.title}</h5>
                            </div>
                            <ChevronRight className={cn(
                              "h-5 w-5 text-muted-foreground transition-transform shrink-0",
                              isExpanded && "rotate-90"
                            )} />
                          </div>

                          {isExpanded && (
                            <div className="mt-4 pt-4 border-t border-border space-y-4">
                              <p className="text-sm text-foreground/80 leading-relaxed leading-6">
                                {node.content}
                              </p>

                              {/* Fork trigger button */}
                              {node.type !== "conclusion" && (
                                <div className="mt-4">
                                  {isForking ? (
                                    <form onSubmit={handleForkSubmit} className="space-y-3 pt-2">
                                      <label className="text-[10px] font-bold text-amber-500 uppercase tracking-wider">
                                        Introduce Counter-Assumption
                                      </label>
                                      <div className="flex gap-2">
                                        <input
                                          value={forkAssumption}
                                          onChange={(e) => setForkAssumption(e.target.value)}
                                          placeholder="E.g. What if authentication keys expire every 5 minutes?"
                                          className="flex-1 rounded-xl border border-border bg-muted/20 px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-muted-foreground/50 text-foreground"
                                        />
                                        <button
                                          type="submit"
                                          disabled={forking || forkAssumption.trim().length < 3}
                                          className="px-3 py-2 rounded-xl bg-primary text-white text-xs font-bold hover:bg-primary/95 disabled:opacity-50"
                                        >
                                          Fork Path
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => setForkNodeId(null)}
                                          className="px-3 py-2 rounded-xl border border-border text-xs text-muted-foreground font-bold hover:text-foreground"
                                        >
                                          Cancel
                                        </button>
                                      </div>
                                    </form>
                                  ) : (
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setForkNodeId(node.id);
                                        setForkAssumption("");
                                      }}
                                      className="inline-flex items-center gap-1.5 text-xs font-bold text-primary hover:underline"
                                    >
                                      <GitFork className="h-3.5 w-3.5" /> Fork from here
                                    </button>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-border bg-muted/10 p-8 text-center text-muted-foreground text-sm">
                  Select a reasoning branch on the left to explore the Visible Chain of Thought.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div className="text-center space-y-2">
        <h2 className="text-3xl font-extrabold text-foreground tracking-tight">Oracle Reasoning Summary</h2>
        <p className="text-muted-foreground text-sm max-w-lg mx-auto">
          Explore a structured analysis outline for complex prompt inquiries. Interrupt and fork paths at any reasoning step.
        </p>
      </div>

      <form onSubmit={handleStart} className="rounded-2xl border border-border bg-card p-6 shadow-sm space-y-6">
        {error && (
          <div className="p-4 rounded-xl border border-rose-500/20 bg-rose-500/5 text-rose-500 text-sm flex items-center gap-2">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="space-y-2">
          <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Inquiry Query</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Type a complex logical challenge, design trade-off, or operational riddle. E.g., 'Is local caching better than federated caching for distributed database sync operations?'"
            className="w-full h-32 rounded-xl border border-border bg-muted/20 p-4 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary resize-none placeholder:text-muted-foreground/60"
          />
          <div className="flex justify-between items-center text-xs text-muted-foreground">
            <span>Minimum 5 characters</span>
            <span>{prompt.length} chars</span>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading || prompt.trim().length < 5}
          className="w-full py-3 px-4 rounded-xl font-bold text-sm text-white bg-primary hover:bg-primary/95 transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Commencing reasoning...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" /> Start Reasoning Chain
            </>
          )}
        </button>
      </form>
    </div>
  );
}
