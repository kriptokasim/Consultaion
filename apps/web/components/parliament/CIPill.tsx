"use client";

import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

type CIPillProps = {
  winRate: number;
  low: number;
  high: number;
  className?: string;
};

export default function CIPill({ winRate, low, high, className }: CIPillProps) {
  const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-semibold text-foreground",
        className,
      )}
      title={`Wilson 95% CI: ${percent(low)} – ${percent(high)}`}
    >
      <span className="flex items-center gap-1">
        <Info className="h-3.5 w-3.5 text-accent-secondary" />
        {percent(winRate)}
      </span>
      <span className="text-[11px] font-medium text-muted-foreground">
        ({percent(low)} – {percent(high)})
      </span>
    </div>
  );
}
