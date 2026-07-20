import type { WorkspaceStage } from "@/lib/workspace/types";
import {
  SUCCESSFUL_STATUSES,
  TERMINAL_STATUSES,
  isSuccessfulRunStatus,
  isTerminalRunStatus,
} from "@/lib/runStatus";

// PS157 Track A: canonical status sets live in @/lib/runStatus.
// These aliases preserve the existing public API of this module.
export const SUCCESSFUL_RUN_STATUSES = SUCCESSFUL_STATUSES;
export const TERMINAL_RUN_STATUSES = TERMINAL_STATUSES;

export { isSuccessfulRunStatus, isTerminalRunStatus };

export type RunPhase =
  | "idle"
  | "creating"
  | "active"
  | "synthesizing"
  | "completed"
  | "failed"
  | "cancelled";

export function deriveRunPhase(
  status: string | null | undefined,
  workspaceStage: WorkspaceStage,
): RunPhase {
  if (!status) return "idle";

  if (status === "cancelled") return "cancelled";
  if (status === "failed") return "failed";
  if (isSuccessfulRunStatus(status)) return "completed";
  if (status === "queued" || status === "scheduled") return "creating";
  if (status === "perspectives_ready") return "active";

  if (workspaceStage === "synthesizing" || workspaceStage === "verifying") {
    return "synthesizing";
  }

  return "active";
}
