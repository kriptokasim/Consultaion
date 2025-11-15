'use client'

import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type LoadingStateProps = {
  label?: string;
  description?: string;
  className?: string;
};

export default function LoadingState({ label = "Loading", description, className }: LoadingStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-3xl border border-stone-200 bg-white/80 p-8 text-center",
        className,
      )}
      aria-live="polite"
      aria-busy="true"
    >
      <Loader2 className="h-6 w-6 animate-spin text-amber-600" />
      <div>
        <p className="text-sm font-semibold text-stone-800">{label}</p>
        {description ? <p className="mt-1 text-xs text-stone-500">{description}</p> : null}
      </div>
    </div>
  );
}
