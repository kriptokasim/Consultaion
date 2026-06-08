"use client";

import React, { useState, useEffect } from "react";
import { 
  ShieldAlert, Cpu, Scale, DollarSign, Settings, 
  AlertTriangle, Info, ChevronRight, ArrowLeft,
  Loader2, CheckCircle2, ShieldAlert as SevereIcon,
  HelpCircle, Copy, Check
} from "lucide-react";
import { apiRequest } from "@/lib/apiClient";
import { cn } from "@/lib/utils";

type RiskIssue = {
  lens: string;
  title: string;
  severity: "high" | "medium" | "low";
  description: string;
  remediation: string;
};

type SessionState = {
  id: string;
  proposal_text: string;
  lenses: string[];
  status: "processing" | "completed";
  issues: RiskIssue[];
  created_at: string;
};

const lensMetadata: Record<string, { label: string; icon: any; color: string; desc: string }> = {
  security: {
    label: "Security",
    icon: ShieldAlert,
    color: "text-rose-500 bg-rose-500/10 border-rose-500/20",
    desc: "Exploits, lack of auth, injection vulnerabilities"
  },
  scaling: {
    label: "Scaling & Perf",
    icon: Cpu,
    color: "text-amber-500 bg-amber-500/10 border-amber-500/20",
    desc: "Bottlenecks, DB contention, memory issues"
  },
  compliance: {
    label: "Compliance & Legal",
    icon: Scale,
    color: "text-teal-500 bg-teal-500/10 border-teal-500/20",
    desc: "GDPR, HIPAA, liability, licensing terms"
  },
  financial: {
    label: "Financial & ROI",
    icon: DollarSign,
    color: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20",
    desc: "CAC, charging errors, margin leakage"
  },
  operations: {
    label: "Operations & SRE",
    icon: Settings,
    color: "text-indigo-500 bg-indigo-500/10 border-indigo-500/20",
    desc: "Ops overhead, recovery path, manual steps"
  }
};

export default function RedTeamWorkspace() {
  const [proposal, setProposal] = useState("");
  const [selectedLenses, setSelectedLenses] = useState<string[]>(["security", "scaling", "compliance"]);
  const [session, setSession] = useState<SessionState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<RiskIssue | null>(null);
  const [copied, setCopied] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<string | null>(null);
  const [lensFilter, setLensFilter] = useState<string | null>(null);

  // Poll for status if processing
  useEffect(() => {
    if (!session || session.status !== "processing") return;

    const interval = setInterval(async () => {
      try {
        const data = await apiRequest<SessionState>({
          path: `/redteam/${session.id}`,
          method: "GET"
        });
        if (data.status === "completed") {
          setSession(data);
        }
      } catch (err: any) {
        console.error("Error polling red team session:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [session]);

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    if (proposal.trim().length < 10) {
      setError("Proposal must be at least 10 characters long.");
      return;
    }
    if (selectedLenses.length === 0) {
      setError("Please select at least one risk lens.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await apiRequest<SessionState & { status: string }>({
        path: "/redteam",
        method: "POST",
        body: {
          proposal_text: proposal,
          lenses: selectedLenses
        }
      });
      setSession({
        id: data.id,
        proposal_text: data.proposal_text,
        lenses: data.lenses,
        status: "processing",
        issues: [],
        created_at: data.created_at
      });
    } catch (err: any) {
      setError(err.message || "Failed to start simulation.");
    } finally {
      setLoading(false);
    }
  };

  const toggleLens = (lens: string) => {
    if (selectedLenses.includes(lens)) {
      setSelectedLenses(selectedLenses.filter(l => l !== lens));
    } else {
      setSelectedLenses([...selectedLenses, lens]);
    }
  };

  const handleCopyRemediation = (remediation: string) => {
    navigator.clipboard.writeText(remediation);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Filter issues
  const filteredIssues = session?.issues.filter(issue => {
    if (severityFilter && issue.severity !== severityFilter) return false;
    if (lensFilter && issue.lens !== lensFilter) return false;
    return true;
  }) || [];

  if (session) {
    const activeLenses = session.lenses;

    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <button 
            onClick={() => {
              setSession(null);
              setSelectedIssue(null);
              setSeverityFilter(null);
              setLensFilter(null);
            }}
            className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Reset Workspace
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

        {session.status === "processing" ? (
          <div className="flex flex-col items-center justify-center py-20 bg-card/40 rounded-2xl border border-border">
            <Loader2 className="h-10 w-10 text-primary animate-spin mb-4" />
            <h3 className="text-lg font-semibold text-foreground">Running Adversarial Simulation</h3>
            <p className="text-sm text-muted-foreground max-w-md text-center mt-2 px-6">
              Reviewer models are performing critiques using the selected lenses: <strong className="text-foreground">{activeLenses.join(", ")}</strong>. This will take a few seconds...
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left Col: Matrix + Filters */}
            <div className="lg:col-span-8 space-y-6">
              {/* Proposal Summary Card */}
              <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
                <h4 className="text-xs font-bold text-accent-secondary uppercase tracking-wider mb-2">Evaluated Proposal</h4>
                <div className="text-sm text-foreground/80 max-h-32 overflow-y-auto whitespace-pre-wrap pr-2 font-mono bg-accent-secondary/5 rounded-xl p-4 border border-accent-secondary/10">
                  {session.proposal_text}
                </div>
              </div>

              {/* Risk Matrix Grid */}
              <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">Risk Matrix View</h4>
                  {(severityFilter || lensFilter) && (
                    <button 
                      onClick={() => {
                        setSeverityFilter(null);
                        setLensFilter(null);
                      }}
                      className="text-xs text-primary font-semibold hover:underline"
                    >
                      Clear Filters
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-4 gap-2 text-center text-xs font-bold uppercase text-muted-foreground mb-1">
                  <div>Lens</div>
                  <div className="text-rose-500">High</div>
                  <div className="text-amber-500">Med</div>
                  <div className="text-blue-500">Low</div>
                </div>

                <div className="space-y-2">
                  {activeLenses.map(lens => {
                    const meta = lensMetadata[lens] || { label: lens, icon: HelpCircle, color: "text-muted-foreground bg-muted" };
                    const Icon = meta.icon;

                    const countBySev = (sev: "high" | "medium" | "low") => {
                      return session.issues.filter(i => i.lens === lens && i.severity === sev).length;
                    };

                    const highCount = countBySev("high");
                    const medCount = countBySev("medium");
                    const lowCount = countBySev("low");

                    return (
                      <div key={lens} className="grid grid-cols-4 gap-2 items-center bg-muted/20 p-2 rounded-xl border border-border/40">
                        <button 
                          onClick={() => setLensFilter(lensFilter === lens ? null : lens)}
                          className={cn(
                            "flex items-center gap-2 text-xs font-semibold px-2 py-1.5 rounded-lg border transition-all text-left",
                            lensFilter === lens 
                              ? "bg-primary/10 text-primary border-primary/20"
                              : "hover:bg-muted text-foreground/85 border-transparent"
                          )}
                        >
                          <Icon className="h-4 w-4 shrink-0" />
                          <span className="truncate">{meta.label}</span>
                        </button>

                        <button 
                          onClick={() => {
                            setLensFilter(lens);
                            setSeverityFilter("high");
                          }}
                          disabled={highCount === 0}
                          className={cn(
                            "py-2 rounded-lg font-bold text-sm transition-all",
                            highCount > 0 
                              ? "bg-rose-500/10 text-rose-500 border border-rose-500/25 hover:bg-rose-500/20"
                              : "bg-muted/30 text-muted-foreground/30 cursor-not-allowed"
                          )}
                        >
                          {highCount}
                        </button>

                        <button 
                          onClick={() => {
                            setLensFilter(lens);
                            setSeverityFilter("medium");
                          }}
                          disabled={medCount === 0}
                          className={cn(
                            "py-2 rounded-lg font-bold text-sm transition-all",
                            medCount > 0 
                              ? "bg-amber-500/10 text-amber-500 border border-amber-500/25 hover:bg-amber-500/20"
                              : "bg-muted/30 text-muted-foreground/30 cursor-not-allowed"
                          )}
                        >
                          {medCount}
                        </button>

                        <button 
                          onClick={() => {
                            setLensFilter(lens);
                            setSeverityFilter("low");
                          }}
                          disabled={lowCount === 0}
                          className={cn(
                            "py-2 rounded-lg font-bold text-sm transition-all",
                            lowCount > 0 
                              ? "bg-blue-500/10 text-blue-500 border border-blue-500/25 hover:bg-blue-500/20"
                              : "bg-muted/30 text-muted-foreground/30 cursor-not-allowed"
                          )}
                        >
                          {lowCount}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Filtered Issues List */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                  Identified Vulnerabilities ({filteredIssues.length})
                </h4>
                {filteredIssues.length === 0 ? (
                  <div className="py-12 text-center bg-card rounded-2xl border border-border text-muted-foreground text-sm">
                    No risk items match your filters.
                  </div>
                ) : (
                  filteredIssues.map((issue, idx) => {
                    const meta = lensMetadata[issue.lens] || { label: issue.lens, icon: HelpCircle };
                    const LensIcon = meta.icon;

                    return (
                      <div 
                        key={idx}
                        onClick={() => setSelectedIssue(issue)}
                        className={cn(
                          "flex items-center justify-between p-4 rounded-xl border cursor-pointer hover:-translate-y-0.5 transition-all bg-card hover:bg-muted/10",
                          issue.severity === "high" && "border-rose-500/20 hover:border-rose-500/40",
                          issue.severity === "medium" && "border-amber-500/20 hover:border-amber-500/40",
                          issue.severity === "low" && "border-blue-500/20 hover:border-blue-500/40"
                        )}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <span className={cn(
                            "p-2 rounded-lg shrink-0",
                            issue.severity === "high" && "bg-rose-500/10 text-rose-500",
                            issue.severity === "medium" && "bg-amber-500/10 text-amber-500",
                            issue.severity === "low" && "bg-blue-500/10 text-blue-500"
                          )}>
                            <LensIcon className="h-4 w-4" />
                          </span>
                          <div className="min-w-0">
                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                              {meta.label} · <span className={cn(
                                issue.severity === "high" && "text-rose-500",
                                issue.severity === "medium" && "text-amber-500",
                                issue.severity === "low" && "text-blue-500"
                              )}>{issue.severity}</span>
                            </p>
                            <h5 className="font-semibold text-foreground truncate">{issue.title}</h5>
                          </div>
                        </div>
                        <ChevronRight className="h-5 w-5 text-muted-foreground shrink-0" />
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Right Col: Deep Dive Drawer/Panel */}
            <div className="lg:col-span-4">
              {selectedIssue ? (
                <div className="rounded-2xl border border-border bg-card p-6 shadow-sm sticky top-6 space-y-6">
                  <div className="flex justify-between items-start gap-4">
                    <div>
                      <span className={cn(
                        "px-2 py-0.5 text-[10px] font-bold rounded-full uppercase tracking-wider border",
                        selectedIssue.severity === "high" && "bg-rose-500/10 text-rose-500 border-rose-500/20",
                        selectedIssue.severity === "medium" && "bg-amber-500/10 text-amber-500 border-amber-500/20",
                        selectedIssue.severity === "low" && "bg-blue-500/10 text-blue-500 border-blue-500/20"
                      )}>
                        {selectedIssue.severity} risk
                      </span>
                      <h4 className="text-lg font-bold text-foreground mt-2">{selectedIssue.title}</h4>
                    </div>
                    <button 
                      onClick={() => setSelectedIssue(null)}
                      className="text-xs text-muted-foreground hover:text-foreground font-semibold"
                    >
                      Close
                    </button>
                  </div>

                  <div>
                    <h5 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">Vulnerability Context</h5>
                    <p className="text-sm text-foreground/80 leading-relaxed bg-muted/20 p-3 rounded-xl border border-border/40">
                      {selectedIssue.description}
                    </p>
                  </div>

                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <h5 className="text-xs font-bold text-emerald-500 uppercase tracking-wider">Remediation Action</h5>
                      <button 
                        onClick={() => handleCopyRemediation(selectedIssue.remediation)}
                        className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
                      >
                        {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                        {copied ? "Copied" : "Copy"}
                      </button>
                    </div>
                    <p className="text-sm text-foreground/90 leading-relaxed font-mono bg-emerald-500/5 p-4 rounded-xl border border-emerald-500/10 whitespace-pre-wrap">
                      {selectedIssue.remediation}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-border bg-muted/10 p-8 text-center text-muted-foreground text-sm sticky top-6">
                  <Info className="h-8 w-8 text-muted-foreground/50 mx-auto mb-3" />
                  Select an identified vulnerability to view its deep-dive analysis and remediation instructions.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="text-center space-y-2">
        <h2 className="text-3xl font-extrabold text-foreground tracking-tight">Red Team Critique Lab</h2>
        <p className="text-muted-foreground text-sm max-w-lg mx-auto">
          Subject your project proposals, system architectures, or product pricing rules to rigorous adversarial scrutiny from autonomous critique personas.
        </p>
      </div>

      <form onSubmit={handleStart} className="rounded-2xl border border-border bg-card p-6 shadow-sm space-y-6">
        {error && (
          <div className="p-4 rounded-xl border border-rose-500/20 bg-rose-500/5 text-rose-500 text-sm flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="space-y-2">
          <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Proposal or System Design</label>
          <textarea
            value={proposal}
            onChange={(e) => setProposal(e.target.value)}
            placeholder="Describe your design, architectural pattern, or business process. E.g., 'We store customer API keys in plaintext in our DB for faster read performance, caching them in Redis without SSL...'"
            className="w-full h-40 rounded-xl border border-border bg-muted/20 p-4 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary resize-none placeholder:text-muted-foreground/60"
          />
          <div className="flex justify-between items-center text-xs text-muted-foreground">
            <span>Minimum 10 characters</span>
            <span>{proposal.length} chars</span>
          </div>
        </div>

        <div className="space-y-3">
          <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground block">Select Risk Lenses</label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.entries(lensMetadata).map(([key, meta]) => {
              const Icon = meta.icon;
              const isSelected = selectedLenses.includes(key);

              return (
                <div 
                  key={key}
                  onClick={() => toggleLens(key)}
                  className={cn(
                    "flex gap-3 p-3 rounded-xl border cursor-pointer hover:border-primary/45 hover:bg-muted/10 transition-all select-none items-start",
                    isSelected 
                      ? "border-primary/30 bg-primary/5" 
                      : "border-border/60"
                  )}
                >
                  <span className={cn(
                    "p-2 rounded-lg shrink-0 mt-0.5 border",
                    isSelected ? meta.color : "bg-muted text-muted-foreground border-transparent"
                  )}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <div>
                    <h5 className="font-semibold text-sm text-foreground">{meta.label}</h5>
                    <p className="text-xs text-muted-foreground mt-0.5">{meta.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <button
          type="submit"
          disabled={loading || proposal.trim().length < 10 || selectedLenses.length === 0}
          className="w-full py-3 px-4 rounded-xl font-bold text-sm text-white bg-primary hover:bg-primary/95 transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Starting Simulation...
            </>
          ) : (
            "Run Adversarial Simulation"
          )}
        </button>
      </form>
    </div>
  );
}
