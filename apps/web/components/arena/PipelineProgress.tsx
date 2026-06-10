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

export function PipelineProgress({ currentStage, elapsedSeconds = 0, className }: PipelineProgressProps) {
  const activeIdx = getStageIndex(currentStage);

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
              <span>{stage.label}</span>
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

export function derivePipelineStage(debate: any, eventTypes: Set<string>): PipelineStage {
  const status = debate?.status;

  if (status === "completed") return "complete";
  if (status === "queued") return "queued";
  if (status === "failed") return "queued";

  const hasArenaStarted = eventTypes.has("arena_started");
  const hasArenaResponse = eventTypes.has("arena_response");
  const hasScore = eventTypes.has("score");
  const hasDivergence = !!debate?.final_meta?.divergence_score;
  const hasSynthesis = eventTypes.has("arena_synthesis") || !!debate?.synthesis_report;
  const hasQualityMeta = !!debate?.synthesis_report?.quality_meta;
  const hasFinal = eventTypes.has("final");

  if (hasFinal || hasQualityMeta) return "complete";
  if (hasSynthesis && hasQualityMeta) return "verifying";
  if (hasSynthesis) return "synthesizing";
  if (hasDivergence) return "divergence_analysis";
  if (hasScore) return "scoring";
  if (hasArenaResponse) return "collecting_responses";
  if (hasArenaStarted) return "models_contacted";
  return "queued";
}
