"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Clock, CheckCircle2, AlertTriangle, Loader2 } from "lucide-react";
import type { DebateSummary } from "@/lib/api/types";
import { isTerminalRunStatus, isSuccessfulRunStatus } from "@/lib/runs/status";

interface RecentRunsRailProps {
  runs: DebateSummary[];
  currentRunId?: string | null;
  maxEntries?: number;
}

function formatTimeAgo(ts?: string | null): string {
  if (!ts) return "";
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function StatusIcon({ status }: { status: string }) {
  if (isSuccessfulRunStatus(status)) {
    return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />;
  }
  if (status === "failed") {
    return <AlertTriangle className="h-3.5 w-3.5 text-red-500" />;
  }
  if (status === "cancelled") {
    return <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />;
  }
  if (isTerminalRunStatus(status)) {
    return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />;
  }
  return <Loader2 className="h-3.5 w-3.5 text-muted-foreground animate-spin" />;
}

export function RecentRunsRail({ runs, currentRunId, maxEntries = 5 }: RecentRunsRailProps) {
  const router = useRouter();
  const displayRuns = runs.slice(0, maxEntries);

  if (displayRuns.length === 0) return null;

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
        <Clock className="h-3.5 w-3.5" />
        Recent Activity
      </h3>
      <div className="space-y-1">
        {displayRuns.map((run) => {
          const isActive = run.id === currentRunId;
          return (
            <button
              key={run.id}
              onClick={() => router.push(`/live?run=${encodeURIComponent(run.id)}`)}
              className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors ${
                isActive
                  ? "bg-primary/10 text-primary border border-primary/20"
                  : "hover:bg-muted/50 text-muted-foreground hover:text-foreground"
              }`}
            >
              <div className="flex items-center gap-2">
                <StatusIcon status={run.status || ""} />
                <span className="truncate flex-1 font-medium">
                  {run.prompt || "Untitled Run"}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-0.5 ml-5">
                <span className="text-[10px] text-muted-foreground">
                  {formatTimeAgo(run.created_at)}
                </span>
                {run.mode && (
                  <span className="text-[10px] text-muted-foreground capitalize">
                    {run.mode}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
