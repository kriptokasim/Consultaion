"use client";

import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-stone-200/70", className)} />;
}

export function DebateCardSkeleton() {
  return (
    <div className="rounded-3xl border border-stone-200 bg-white/80 p-6 shadow-inner">
      <Skeleton className="h-4 w-24 rounded-full" />
      <Skeleton className="mt-4 h-6 w-3/4 rounded-full" />
      <Skeleton className="mt-2 h-6 w-2/3 rounded-full" />
      <div className="mt-4 space-y-2">
        <Skeleton className="h-3 w-full rounded-full" />
        <Skeleton className="h-3 w-11/12 rounded-full" />
        <Skeleton className="h-3 w-3/4 rounded-full" />
      </div>
    </div>
  );
}
