"use client";

import React from "react";
import { Check, Loader2, Circle, Pause } from "lucide-react";
import { cn } from "@/lib/utils";

export type PipelineStage =
  | "queued"
  | "models_contacted"
  | "collecting_responses"
  | "perspectives_ready"
  | "scoring"
  | "divergence_analysis"
  | "synthesizing"
  | "verifying"
  | "complete";

interface StageInfo {
  key: PipelineStage;
  label: string;
}

const ALL_STAGES: StageInfo[] = [
  { key: "queued", label: "Run created" },
  { key: "models_contacted", label: "Models contacted" },
  { key: "collecting_responses", label: "Waiting for model responses" },
  { key: "perspectives_ready", label: "Perspectives ready (Paused)" },
  { key: "scoring", label: "Scoring responses" },
  { key: "divergence_analysis", label: "Analyzing divergence" },
  { key: "synthesizing", label: "Synthesizing decision report" },
  { key: "verifying", label: "Verifying report" },
  { key: "complete", label: "Complete" },
];

interface PipelineProgressProps {
  currentStage: PipelineStage;
  elapsedSeconds?: number;
  className?: string;
  responsesReceived?: number;
  modelsExpected?: number;
  scoresReceived?: number;
  variant?: "full" | "compact";
}

function getStageIndex(stage: PipelineStage): number {
  return ALL_STAGES.findIndex((s) => s.key === stage);
}

function StageIcon({ state, stageKey }: { state: "done" | "active" | "pending"; stageKey: PipelineStage }) {
  if (state === "done") {
    return <Check className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />;
  }
  if (state === "active") {
    if (stageKey === "perspectives_ready") {
      return <Pause className="h-4 w-4 text-amber-500 dark:text-amber-400 animate-pulse" />;
    }
    return <Loader2 className="h-4 w-4 text-amber-600 dark:text-amber-400 animate-spin" />;
  }
  return <Circle className="h-4 w-4 text-stone-300 dark:text-stone-600" />;
}

export function PipelineProgress({
  currentStage,
  elapsedSeconds = 0,
  className,
  responsesReceived = 0,
  modelsExpected = 4,
  scoresReceived = 0,
  variant = "full",
}: PipelineProgressProps) {
  const activeIdx = getStageIndex(currentStage);

  const getStageLabel = (stage: StageInfo) => {
    if (stage.key === "collecting_responses") {
      if (responsesReceived === 0) {
        return "Waiting for model responses";
      }
      if (responsesReceived < modelsExpected) {
        return `Collecting model responses (${responsesReceived}/${modelsExpected} received)`;
      }
      return "All model responses collected";
    }
    if (stage.key === "scoring") {
      if (scoresReceived > 0 && scoresReceived < modelsExpected) {
        return `Evaluating responses (${scoresReceived}/${modelsExpected} scored)`;
      }
    }
    return stage.label;
  };

  const formatProgressDuration = (sec: number): string => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const activeStageLabel = activeIdx >= 0 ? getStageLabel(ALL_STAGES[activeIdx]) : "Idle";

  const [isExpanded, setIsExpanded] = React.useState(false);

  if (variant === "compact") {
    return (
      <div className={cn("rounded-2xl border border-stone-200 bg-white/85 p-3.5 shadow-sm dark:border-stone-800 dark:bg-stone-900/75 backdrop-blur-sm", className)}>
        {/* Horizontal dots rail */}
        <div className="flex items-center w-full gap-1 mb-2.5 cursor-pointer" onClick={() => setIsExpanded(!isExpanded)}>
          {ALL_STAGES.map((stage, idx) => {
            const isDone = idx < activeIdx;
            const isActive = idx === activeIdx;
            return (
              <React.Fragment key={stage.key}>
                {idx > 0 && (
                  <div
                    className={cn(
                      "h-0.5 flex-1 transition-all duration-300",
                      isDone || isActive ? "bg-emerald-500/70 dark:bg-emerald-450/60" : "bg-stone-200 dark:bg-stone-800"
                    )}
                  />
                )}
                <div
                  className={cn(
                    "w-2.5 h-2.5 rounded-full transition-all duration-300 shrink-0",
                    isDone && "bg-emerald-500 dark:bg-emerald-400",
                    isActive && "bg-amber-500 dark:bg-amber-400 animate-pulse scale-110 shadow-sm shadow-amber-500/30",
                    !isDone && !isActive && "bg-stone-200 dark:bg-stone-800"
                  )}
                  title={stage.label}
                />
              </React.Fragment>
            );
          })}
        </div>
        {/* Description line */}
        <div className="flex items-center justify-between text-xs cursor-pointer select-none" onClick={() => setIsExpanded(!isExpanded)}>
          <div className="flex items-center gap-2 text-stone-700 dark:text-stone-300 font-medium">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-ping" />
            <span>Step {activeIdx + 1}/9:</span>
            <span className="text-stone-900 dark:text-stone-100 font-semibold">{activeStageLabel}</span>
          </div>
          <div className="flex items-center gap-1.5 text-stone-500 dark:text-stone-400 font-mono font-semibold">
            <span>{formatProgressDuration(elapsedSeconds)}</span>
            <span className="text-[10px] text-muted-foreground bg-stone-100 dark:bg-stone-800 px-1 py-0.5 rounded transition hover:bg-stone-200 dark:hover:bg-stone-700">
              {isExpanded ? "Hide Details" : "Show Details"}
            </span>
          </div>
        </div>

        {isExpanded && (
          <div className="mt-4 pt-3 border-t border-stone-100 dark:border-stone-800 space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
            {ALL_STAGES.map((stage, idx) => {
              let state: "done" | "active" | "pending" = "pending";
              if (idx < activeIdx) state = "done";
              else if (idx === activeIdx) state = "active";

              return (
                <div
                  key={stage.key}
                  className={cn(
                    "flex items-center gap-2 text-xs transition-colors",
                    state === "done" && "text-emerald-700 dark:text-emerald-400",
                    state === "active" && "text-amber-700 dark:text-amber-400 font-medium",
                    state === "pending" && "text-stone-400 dark:text-stone-600",
                  )}
                >
                  <StageIcon state={state} stageKey={stage.key} />
                  <span>{getStageLabel(stage)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={cn("rounded-2xl border border-stone-200 bg-white/80 p-4 shadow-sm dark:border-stone-700 dark:bg-stone-900/60", className)}>
      <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400 mb-3">
        Pipeline Progress
      </p>
      <div className="space-y-2">
        {ALL_STAGES.map((stage, idx) => {
          let state: "done" | "active" | "pending" = "pending";
          if (idx < activeIdx) state = "done";
          else if (idx === activeIdx) state = "active";

          return (
            <div
              key={stage.key}
              className={cn(
                "flex items-center gap-2 text-sm transition-colors",
                state === "done" && "text-emerald-700 dark:text-emerald-400",
                state === "active" && "text-amber-700 dark:text-amber-400 font-medium",
                state === "pending" && "text-stone-400 dark:text-stone-600",
              )}
            >
              <StageIcon state={state} stageKey={stage.key} />
              <span>{getStageLabel(stage)}</span>
            </div>
          );
        })}
      </div>
      <div className="mt-4 space-y-1">
        <p className="text-xs text-stone-500 dark:text-stone-400">
          High-quality Arena runs may take 30–90 seconds depending on model/provider latency.
        </p>
        {elapsedSeconds > 45 && elapsedSeconds <= 90 && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            Still working. Some providers are taking longer than usual.
          </p>
        )}
        {elapsedSeconds > 90 && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            This run is taking longer than expected. You can leave this page and return from Runs.
          </p>
        )}
      </div>
    </div>
  );
}

export function derivePipelineStage(debate: any, eventTypes: Set<string>, liveResponseCount?: number): PipelineStage {
  const status = debate?.status;

  if (["completed", "success", "completed_budget"].includes(status)) return "complete";
  if (status === "failed") return "queued";
  if (status === "queued") return "queued";
  if (status === "perspectives_ready") return "perspectives_ready";

  // Check persisted properties on the debate model
  const hasQualityMeta = !!debate?.final_meta?.synthesis_report?.quality_meta || !!debate?.synthesis_report?.quality_meta;
  const hasSynthesis = !!debate?.final_meta?.synthesis_report || !!debate?.synthesis_report || eventTypes.has("arena_synthesis") || eventTypes.has("synthesis");
  const hasDivergence = typeof debate?.final_meta?.divergence_score === "number" || typeof debate?.divergence_score === "number" || eventTypes.has("divergence_analysis");
  const hasScore = !!debate?.final_meta?.scores || !!debate?.scores || eventTypes.has("score");

  // Model responses check
  const responseCount = debate?.final_meta?.successful_count || debate?.messages?.filter((m: any) => m.role === "arena_response" || m.role === "message" || m.role === "candidate").length || liveResponseCount || 0;
  const hasArenaResponse = responseCount > 0 || eventTypes.has("arena_response") || eventTypes.has("message");
  const hasArenaStarted = eventTypes.has("arena_started") || hasArenaResponse;

  if (hasSynthesis && hasQualityMeta) return "verifying";
  if (hasSynthesis) return "synthesizing";
  if (hasDivergence) return "divergence_analysis";
  if (hasScore) return "scoring";

  const expectedModels =
    debate?.final_meta?.models?.length ||
    (debate?.config as any)?.models?.length ||
    debate?.model_count ||
    4;

  if (hasArenaResponse) {
    if (responseCount >= expectedModels) return "scoring";
    return "collecting_responses";
  }
  if (hasArenaStarted) return "models_contacted";
  return "queued";
}
