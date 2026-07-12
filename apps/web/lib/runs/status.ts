import type { WorkspaceStage } from "@/lib/workspace/types";

export const SUCCESSFUL_RUN_STATUSES = new Set([
  "completed",
  "completed_with_warnings",
  "completed_budget",
  "success",
]);

export const TERMINAL_RUN_STATUSES = new Set([
  "completed",
  "completed_with_warnings",
  "completed_budget",
  "success",
  "failed",
  "cancelled",
]);

export function isSuccessfulRunStatus(status?: string | null): boolean {
  return !!status && SUCCESSFUL_RUN_STATUSES.has(status);
}

export function isTerminalRunStatus(status?: string | null): boolean {
  return !!status && TERMINAL_RUN_STATUSES.has(status);
}

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
