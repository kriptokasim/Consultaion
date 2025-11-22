"use client"

import { cn } from "@/lib/utils";

type SkeletonLoaderProps = {
  className?: string;
  lines?: number;
};

export function SkeletonLoader({ className, lines = 1 }: SkeletonLoaderProps) {
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
