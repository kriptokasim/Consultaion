"use client";

import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-amber-100/70 dark:bg-amber-900/40", className)} />;
}

export function DebateCardSkeleton() {
  return (
    <div className="rounded-3xl border border-amber-200/70 bg-amber-50/70 p-6 shadow-[0_12px_28px_rgba(112,73,28,0.12)] dark:border-amber-900/40 dark:bg-amber-950/30">
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

export function DebateListSkeleton() {
  return (
    <div className="overflow-hidden rounded-2xl border border-amber-200/70 bg-white/90 shadow-[0_18px_40px_rgba(112,73,28,0.12)]">
      <div className="divide-y divide-amber-100/80">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-center gap-4 px-5 py-4">
            <Skeleton className="h-10 w-10 rounded-xl" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-3/4 rounded-full" />
              <Skeleton className="h-3 w-1/2 rounded-full" />
            </div>
            <Skeleton className="h-6 w-16 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}
