import type { HTMLAttributes } from "react";

const statusColors: Record<string, string> = {
  running: "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800 animate-[pulse-soft_2s_ease-in-out_infinite]",
  completed: "bg-accent-secondary/10 text-accent-secondary border-accent-secondary/20",
  idle: "bg-muted text-muted-foreground border-border",
  error: "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800",
};

interface StatusPillProps extends HTMLAttributes<HTMLSpanElement> {
  status?: "running" | "completed" | "idle" | "error";
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
      {label ?? status}
    </span>
  );
}
