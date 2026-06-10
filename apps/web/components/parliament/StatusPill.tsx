import type { HTMLAttributes } from "react";

export type ArenaRunUiState =
  | "idle"
  | "creating"
  | "created"
  | "redirecting"
  | "queued"
  | "running"
  | "streaming"
  | "synthesis_pending"
  | "complete"
  | "recoverable_error"
  | "terminal_error";

const statusColors: Record<string, string> = {
  idle: "bg-muted text-muted-foreground border-border",
  creating: "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800",
  created: "bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-800",
  redirecting: "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800",
  queued: "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800",
  running: "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800 animate-[pulse-soft_2s_ease-in-out_infinite]",
  streaming: "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800 animate-[pulse-soft_2s_ease-in-out_infinite]",
  synthesis_pending: "bg-violet-100 text-violet-700 border-violet-200 dark:bg-violet-900/30 dark:text-violet-300 dark:border-violet-800",
  complete: "bg-accent-secondary/10 text-accent-secondary border-accent-secondary/20",
  recoverable_error: "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800",
  terminal_error: "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800",
};

const statusLabels: Record<string, string> = {
  idle: "idle",
  creating: "Creating run",
  created: "Run created",
  redirecting: "Opening live results",
  queued: "Queued",
  running: "Running",
  streaming: "Collecting responses",
  synthesis_pending: "Synthesizing report",
  complete: "Complete",
  recoverable_error: "Connection interrupted",
  terminal_error: "Failed",
};

interface StatusPillProps extends HTMLAttributes<HTMLSpanElement> {
  status?: ArenaRunUiState;
  label?: string;
}

export default function StatusPill({
  status = "idle",
  label,
  className = "",
  ...rest
}: StatusPillProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-4 py-1 text-xs font-semibold uppercase tracking-wide transition-all duration-200 ease-out ${statusColors[status] ?? statusColors.idle} ${className}`}
      {...rest}
    >
      <span className="h-2 w-2 rounded-full bg-current" />
      {label ?? statusLabels[status] ?? status}
    </span>
  );
}
