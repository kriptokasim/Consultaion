import type { WorkspaceStage } from "./types";

export function deriveWorkspaceStage(
  debate: any,
  eventTypes: Set<string>,
  liveResponseCount?: number
): WorkspaceStage {
  const status = debate?.status;

  if (["completed", "success", "completed_budget"].includes(status)) return "complete";
  if (status === "failed") return "failed";
  if (status === "queued") return "idle";
  if (status === "scheduled") return "creating";

  if (status === "perspectives_ready") return "perspectives_ready";

  const hasQualityMeta =
    !!debate?.final_meta?.synthesis_report?.quality_meta ||
    !!debate?.synthesis_report?.quality_meta;
  const hasSynthesis =
    !!debate?.final_meta?.synthesis_report ||
    !!debate?.synthesis_report ||
    eventTypes.has("arena_synthesis") ||
    eventTypes.has("synthesis");
  const hasDivergence =
    typeof debate?.final_meta?.divergence_score === "number" ||
    typeof debate?.divergence_score === "number" ||
    eventTypes.has("divergence_analysis");
  const hasScore =
    !!debate?.final_meta?.scores ||
    !!debate?.scores ||
    eventTypes.has("score");

  const responseCount =
    debate?.final_meta?.successful_count ||
    debate?.messages?.filter(
      (m: any) =>
        m.role === "arena_response" || m.role === "message" || m.role === "candidate"
    ).length ||
    liveResponseCount ||
    0;
  const hasArenaResponse =
    responseCount > 0 ||
    eventTypes.has("arena_response") ||
    eventTypes.has("message");
  const hasArenaStarted = eventTypes.has("arena_started") || hasArenaResponse;

  if (hasSynthesis && hasQualityMeta) return "verifying";
  if (hasSynthesis) return "synthesizing";
  if (hasDivergence) return "analyzing_divergence";
  if (hasScore) return "scoring";

  const expectedModels =
    debate?.final_meta?.models?.length ||
    (debate?.config as any)?.models?.length ||
    debate?.model_count ||
    4;

  if (hasArenaResponse) {
    if (responseCount >= expectedModels) return "scoring";
    return "collecting_perspectives";
  }
  if (hasArenaStarted) return "contacting_models";

  return "idle";
}
