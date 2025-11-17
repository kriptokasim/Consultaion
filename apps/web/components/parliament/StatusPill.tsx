import type { HTMLAttributes } from "react";

const statusColors: Record<string, string> = {
  running: "bg-emerald-100 text-emerald-700 border-emerald-200 animate-[pulse-soft_2s_ease-in-out_infinite]",
  completed: "bg-amber-100 text-amber-700 border-amber-200",
  idle: "bg-stone-100 text-stone-600 border-stone-200",
  error: "bg-red-100 text-red-700 border-red-200",
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
