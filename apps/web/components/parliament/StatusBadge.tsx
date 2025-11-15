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
    className: "border-emerald-200 bg-emerald-50 text-emerald-800",
  },
  running: {
    label: "Running",
    icon: <Clock3 className="h-3.5 w-3.5" />,
    className: "border-amber-200 bg-amber-50 text-amber-800",
  },
  queued: {
    label: "Queued",
    icon: <PauseCircle className="h-3.5 w-3.5" />,
    className: "border-stone-200 bg-stone-50 text-stone-700",
  },
  failed: {
    label: "Failed",
    icon: <XCircle className="h-3.5 w-3.5" />,
    className: "border-rose-200 bg-rose-50 text-rose-800",
  },
  default: {
    label: "Unknown",
    icon: <AlertCircle className="h-3.5 w-3.5" />,
    className: "border-stone-200 bg-white text-stone-600",
  },
};

export default function StatusBadge({ status }: { status?: string | null }) {
  const variant = (status ? STATUS_MAP[status] : undefined) ?? STATUS_MAP.default;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide",
        variant.className,
      )}
    >
      {variant.icon}
      {variant.label}
    </span>
  );
}
