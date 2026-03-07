"use client";

import { AlertCircle, CheckCircle2, Clock3, PauseCircle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_MAP: Record<
  string,
  { label: string; icon: React.ReactNode; className: string }
> = {
  completed: {
    label: "Completed",
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
    className:
      "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300",
  },
  running: {
    label: "Running",
    icon: <Clock3 className="h-3.5 w-3.5" />,
    className:
      "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-700 dark:bg-amber-950/60 dark:text-amber-300",
  },
  queued: {
    label: "Queued",
    icon: <PauseCircle className="h-3.5 w-3.5" />,
    className:
      "border-stone-200 bg-stone-50 text-stone-700 dark:border-border dark:bg-muted dark:text-muted-foreground",
  },
  scheduled: {
    label: "Scheduled",
    icon: <PauseCircle className="h-3.5 w-3.5" />,
    className:
      "border-stone-200 bg-stone-50 text-stone-700 dark:border-border dark:bg-muted dark:text-muted-foreground",
  },
  failed: {
    label: "Failed",
    icon: <XCircle className="h-3.5 w-3.5" />,
    className:
      "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-800 dark:bg-rose-950/60 dark:text-rose-300",
  },
  completed_budget: {
    label: "Completed (budget)",
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
    className:
      "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300",
  },
  default: {
    label: "Unknown",
    icon: <AlertCircle className="h-3.5 w-3.5" />,
    className:
      "border-stone-200 bg-white text-stone-600 dark:border-border dark:bg-card dark:text-muted-foreground",
  },
};

export default function StatusBadge({
  status,
  className,
}: {
  status?: string | null;
  className?: string;
}) {
  const variant = (status ? STATUS_MAP[status] : undefined) ?? STATUS_MAP.default;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide",
        variant.className,
        className,
      )}
    >
      {variant.icon}
      {variant.label}
    </span>
  );
}
