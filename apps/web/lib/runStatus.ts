/**
 * PS157 Track A — Canonical Run Status Contract.
 *
 * Single source of truth for run (debate) status semantics on the frontend.
 * Mirrors the backend `DebateStatus` enum (apps/api/models.py) and the legacy
 * terminal aliases (`completed_budget`, `success`) still present in
 * historical data.
 *
 * Canonical statuses:
 * - Active:   queued, scheduled, running, perspectives_ready
 * - Terminal: completed, completed_with_warnings, completed_budget, success,
 *             failed, cancelled
 */

export const RUN_STATUSES = [
  "queued",
  "scheduled",
  "running",
  "perspectives_ready",
  "completed",
  "completed_with_warnings",
  "completed_budget",
  "success",
  "failed",
  "cancelled",
] as const;

export type RunStatus = (typeof RUN_STATUSES)[number];

/** Active statuses — the run is still in progress (per backend DebateStatus). */
export const ACTIVE_STATUSES: ReadonlySet<string> = new Set<string>([
  "queued",
  "scheduled",
  "running",
  "perspectives_ready",
]);

/**
 * Terminal statuses — the run has reached a final state. No further events,
 * polling, or streaming should be expected.
 */
export const TERMINAL_STATUSES: ReadonlySet<string> = new Set<string>([
  "completed",
  "completed_with_warnings",
  "completed_budget",
  "success",
  "failed",
  "cancelled",
]);

/**
 * Successful statuses — terminal states where the run produced a usable
 * result (synthesis/report may exist).
 */
export const SUCCESSFUL_STATUSES: ReadonlySet<string> = new Set<string>([
  "completed",
  "completed_with_warnings",
  "completed_budget",
  "success",
]);

export function isActiveRunStatus(status?: string | null): boolean {
  return !!status && ACTIVE_STATUSES.has(status);
}

export function isTerminalRunStatus(status?: string | null): boolean {
  return !!status && TERMINAL_STATUSES.has(status);
}

export function isSuccessfulRunStatus(status?: string | null): boolean {
  return !!status && SUCCESSFUL_STATUSES.has(status);
}
