"use client";

import React from "react";
import { Loader2 } from "lucide-react";
import type { DebateDetail, PersistedModelResponse, DebateEvent } from "@/lib/api/types";
import type { StreamingModelBuffer } from "@/lib/streaming/types";
import type { SSEStatus } from "@/lib/sse";
import type { ResponsesState, TimelineState } from "@/hooks/useRunWorkspace";
import type { WorkspaceStage } from "@/lib/workspace/types";
import type { DebateSummary } from "@/lib/api/types";
import ArenaRunView from "./ArenaRunView";
import { DashboardRunsHistory } from "@/components/dashboard/DashboardRunsHistory";

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
  onRefetch?: () => void;
  profile?: any;
  recentRuns?: DebateSummary[];
  recentRunsLoading?: boolean;
  onNewRun?: () => void;
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
  onRefetch,
  profile,
  recentRuns,
  recentRunsLoading,
  onNewRun,
}: ArenaRunContentProps) {
  return (
    <div className="flex flex-col gap-6 pb-8">
      {/* Polling fallback indicator */}
      {isPollingFallback && (
        <div className="flex items-center gap-2 px-4 py-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800 rounded-lg">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Connection interrupted — using polling fallback</span>
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

        {/* Latest Activity rail — 1/4 on wide displays, below on smaller */}
        {surface === "live" && recentRuns && recentRuns.length > 0 && (
          <div className="col-span-1 xl:col-span-1">
            <div className="xl:sticky xl:top-24">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Latest Activity
              </h3>
              <DashboardRunsHistory
                debates={recentRuns.slice(0, 5)}
                debatesLoading={recentRunsLoading ?? false}
                onNewRun={onNewRun ?? (() => {})}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
