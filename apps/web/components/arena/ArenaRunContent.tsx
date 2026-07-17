"use client";

import React, { useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";
import type { DebateDetail, PersistedModelResponse, DebateEvent } from "@/lib/api/types";
import type { StreamingModelBuffer } from "@/lib/streaming/types";
import type { SSEStatus } from "@/lib/sse";
import type { ResponsesState, TimelineState } from "@/hooks/useRunWorkspace";
import type { WorkspaceStage } from "@/lib/workspace/types";
import type { DebateSummary } from "@/lib/api/types";
import ArenaRunView from "./ArenaRunView";
import { RecentRunsRail } from "./RecentRunsRail";

export interface ArenaRunContentProps {
  debate: DebateDetail;
  events: DebateEvent[];
  responses: PersistedModelResponse[];
  streamingBuffers: Map<string, StreamingModelBuffer>;
  isTerminal: boolean;
  responsesState: ResponsesState;
  responsesError?: string | null;
  timelineState: TimelineState;
  workspaceStage: WorkspaceStage;
  elapsedSeconds: number;
  sseStatus: SSEStatus;
  isPollingFallback: boolean;
  surface: "standalone" | "live";
  onRetry?: () => void;
  onContinue?: () => void;
  isContinuing?: boolean;
  onRefetch?: () => void;
  profile?: any;
  recentRuns?: DebateSummary[];
  recentRunsLoading?: boolean;
  onNewRun?: () => void;
  failure?: {
    title: string;
    message: string;
    code?: string;
    correlationId?: string;
    retryable: boolean;
  };
}

export function ArenaRunContent({
  debate,
  events,
  responses,
  streamingBuffers,
  isTerminal,
  responsesState,
  responsesError,
  timelineState,
  workspaceStage,
  elapsedSeconds,
  sseStatus,
  isPollingFallback,
  surface,
  onRetry,
  onContinue,
  isContinuing,
  onRefetch,
  profile,
  recentRuns,
  recentRunsLoading,
  onNewRun,
  failure,
}: ArenaRunContentProps) {
  // Track F: Auto-continue on perspectives_ready for live surface
  const autoContinuedRunRef = useRef<string | null>(null);
  useEffect(() => {
    if (surface !== "live") return;
    if (isTerminal || isContinuing) return;
    if (workspaceStage !== "perspectives_ready") return;
    if (!onContinue) return;
    if (autoContinuedRunRef.current === debate.id) return;
    autoContinuedRunRef.current = debate.id;
    onContinue();
  }, [surface, isTerminal, isContinuing, workspaceStage, onContinue, debate.id]);

  return (
    <div className="flex flex-col gap-6 pb-8">
      {/* Polling fallback indicator */}
      {isPollingFallback && (
        <div className="flex items-center gap-2 px-4 py-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800 rounded-lg">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Connection interrupted — using polling fallback</span>
        </div>
      )}

      {/* Track H: Inline failure banner */}
      {failure && (
        <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4">
          <div className="flex items-start gap-3">
            <div className="shrink-0 rounded-lg bg-red-100 dark:bg-red-800/50 p-2 text-red-600 dark:text-red-400">
              <Loader2 className="h-4 w-4" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-red-800 dark:text-red-200">{failure.title}</h3>
              <p className="text-xs text-red-600 dark:text-red-400 mt-1">{failure.message}</p>
              {failure.code && (
                <p className="text-xs font-mono text-red-500 dark:text-red-300 mt-1">
                  Failure: {failure.code}
                  {failure.correlationId && <> · ID: {failure.correlationId}</>}
                </p>
              )}
            </div>
            {failure.retryable && onRetry && (
              <button
                onClick={onRetry}
                className="shrink-0 px-3 py-1.5 rounded-lg bg-red-100 dark:bg-red-800/50 text-xs font-medium text-red-700 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-700/50 transition-colors"
              >
                Retry Run
              </button>
            )}
          </div>
        </div>
      )}

      {/* Run status bar */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="capitalize">{workspaceStage.replace(/_/g, " ")}</span>
        <span>{elapsedSeconds}s</span>
        {surface === "live" && (
          <span className={sseStatus === "connected" ? "text-emerald-600" : "text-amber-600"}>
            {sseStatus === "connected" ? "Live" : "Reconnecting..."}
          </span>
        )}
      </div>

      {/* Track J: Desktop two-column layout with Latest Activity rail */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        {/* Main content — 3/4 on wide displays */}
        <div className="col-span-1 xl:col-span-3">
          <ArenaRunView
            debate={debate}
            events={events}
            responses={responses}
            streamingBuffers={streamingBuffers}
            isTerminal={isTerminal}
            responsesState={responsesState}
            responsesError={responsesError}
            timelineState={timelineState}
            presentation={surface === "live" ? "live" : "historical"}
            onRefetch={onRefetch}
            profile={profile}
          />
        </div>

        {/* Track J: Latest Activity rail — 1/4 on wide displays, below on smaller */}
        {surface === "live" && recentRuns && recentRuns.length > 0 && (
          <div className="col-span-1 xl:col-span-1">
            <div className="xl:sticky xl:top-24">
              <RecentRunsRail
                runs={recentRuns}
                currentRunId={debate.id}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
