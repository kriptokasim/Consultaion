"use client";

import { Check, Loader2, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

export type PipelineStage =
  | "queued"
  | "models_contacted"
  | "collecting_responses"
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
}

function getStageIndex(stage: PipelineStage): number {
  return ALL_STAGES.findIndex((s) => s.key === stage);
}

function StageIcon({ state }: { state: "done" | "active" | "pending" }) {
  if (state === "done") {
    return <Check className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />;
  }
  if (state === "active") {
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
              <StageIcon state={state} />
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

  if (status === "completed") return "complete";
  if (status === "failed") return "queued";
  if (status === "queued") return "queued";

  // Check persisted properties on the debate model
  const hasQualityMeta = !!debate?.final_meta?.synthesis_report?.quality_meta || !!debate?.synthesis_report?.quality_meta;
  const hasSynthesis = !!debate?.final_meta?.synthesis_report || !!debate?.synthesis_report || eventTypes.has("arena_synthesis") || eventTypes.has("synthesis");
  const hasDivergence = typeof debate?.final_meta?.divergence_score === "number" || typeof debate?.divergence_score === "number" || eventTypes.has("divergence_analysis");
  const hasScore = !!debate?.final_meta?.scores || !!debate?.scores || eventTypes.has("score");

  // Model responses check
  const responseCount = debate?.final_meta?.successful_count || debate?.messages?.filter((m: any) => m.role === "arena_response" || m.role === "message" || m.role === "candidate").length || liveResponseCount || 0;
  const hasArenaResponse = responseCount > 0 || eventTypes.has("arena_response") || eventTypes.has("message");
  const hasArenaStarted = eventTypes.has("arena_started") || hasArenaResponse;

  if (hasQualityMeta) return "complete";
  if (hasSynthesis && hasQualityMeta) return "verifying";
  if (hasSynthesis) return "synthesizing";
  if (hasDivergence) return "divergence_analysis";
  if (hasScore) return "scoring";
  if (hasArenaResponse) return "collecting_responses";
  if (hasArenaStarted) return "models_contacted";
  return "queued";
}
