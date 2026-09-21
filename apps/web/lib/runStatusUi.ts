/**
 * New UX status vocabulary — maps the granular backend-mirrored RunStatus
 * (apps/web/lib/runStatus.ts) and the workspace hook's own transport-level
 * status onto the four canonical labels from DESIGN-SPEC/SCREEN-SPEC:
 * Live, Closed, Needs you, Failed.
 *
 * This does not replace RUN_STATUSES; it is a presentation-only projection.
 */

export type UiRunStatus = "live" | "closed" | "needsYou" | "failed";

const CLOSED_STATUSES = new Set<string>([
  "completed",
  "completed_with_warnings",
  "completed_budget",
  "success",
  "cancelled",
]);

const LIVE_STATUSES = new Set<string>([
  "idle",
  "loading",
  "streaming",
  "polling",
  "queued",
  "scheduled",
  "running",
  "perspectives_ready",
]);

export interface ToUiRunStatusOptions {
  /** A finalized report/verdict exists for this run. */
  hasReport?: boolean;
  /** The workspace has a recoverable error (continueRun/retryRun available). */
  hasError?: boolean;
}

export function toUiRunStatus(
  status: string | null | undefined,
  options: ToUiRunStatusOptions = {},
): UiRunStatus {
  if (status === "failed") return "failed";
  if (options.hasReport) return "closed";
  if (options.hasError) return "needsYou";
  if (status && CLOSED_STATUSES.has(status)) return "closed";
  if (status && LIVE_STATUSES.has(status)) return "live";
  return "live";
}

export const UI_RUN_STATUS_LABEL_KEYS: Record<UiRunStatus, string> = {
  live: "status.live",
  closed: "status.closed",
  needsYou: "status.needsYou",
  failed: "status.failed",
};
