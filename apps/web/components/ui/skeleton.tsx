"use client";

import { cn } from "@/lib/utils";

export interface SkeletonProps {
  className?: string;
  variant?: "pulse" | "shimmer";
}

export function Skeleton({ className, variant = "pulse" }: SkeletonProps) {
  if (variant === "shimmer") {
    return <div className={cn("skeleton skeleton-shimmer rounded-lg", className)} />;
  }
  return <div className={cn("animate-pulse rounded-md bg-amber-100/70 dark:bg-amber-900/40", className)} />;
}

export type SkeletonLoaderProps = {
  className?: string;
  lines?: number;
  count?: number;
  variant?: "text" | "circle" | "rect";
};

export function SkeletonLoader({
  className,
  lines = 1,
  count,
  variant,
}: SkeletonLoaderProps) {
  // If count or variant are specified, use the count/variant logic
  if (count !== undefined || variant !== undefined) {
    const finalCount = count ?? 1;
    const finalVariant = variant ?? "rect";
    const items = Array.from({ length: finalCount });
    return (
      <>
        {items.map((_, idx) => (
          <div
            key={idx}
            className={cn(
              "animate-pulse rounded-lg bg-muted/50",
              finalVariant === "circle" && "rounded-full",
              finalVariant === "text" && "h-4 w-3/4",
              finalVariant === "rect" && "h-12 w-full",
              className
            )}
          />
        ))}
      </>
    );
  }

  // Fallback to the lines logic
  if (lines <= 1) {
    return <div className={cn("skeleton skeleton-shimmer rounded-lg", className)} />;
  }

  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, idx) => (
        <div
          key={idx}
          className={cn("skeleton skeleton-shimmer rounded-lg", className, idx === lines - 1 ? "w-2/3" : "w-full")}
        />
      ))}
    </div>
  );
}

export default SkeletonLoader;

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

export function ModelSelectorSkeleton() {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="flex items-start gap-3 rounded-xl border-2 border-amber-100 bg-white p-3 dark:border-amber-900/40 dark:bg-stone-900"
        >
          <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 border-amber-200 dark:border-amber-800">
            <Skeleton className="h-2 w-2 rounded-full" />
          </div>
          <div className="flex-1 space-y-1">
            <Skeleton className="h-4 w-3/4 rounded" />
            <Skeleton className="h-3 w-1/2 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="space-y-4 rounded-lg border border-border p-6">
      <SkeletonLoader variant="text" className="h-6 w-1/3" />
      <div className="space-y-3">
        <SkeletonLoader variant="text" className="h-4 w-full" />
        <SkeletonLoader variant="text" className="h-4 w-5/6" />
      </div>
      <SkeletonLoader variant="rect" className="h-8 w-24" />
    </div>
  );
}

export function TableSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, idx) => (
        <div key={idx} className="flex items-center gap-4 rounded-lg border border-border p-4">
          <SkeletonLoader variant="circle" className="h-10 w-10 flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <SkeletonLoader variant="text" className="h-4 w-1/3" />
            <SkeletonLoader variant="text" className="h-3 w-1/4" />
          </div>
          <SkeletonLoader variant="text" className="h-4 w-20" />
        </div>
      ))}
    </div>
  );
}
