"use client";

import { DebateCardSkeleton } from "@/components/ui/skeleton";

export default function RunsLoading() {
  return (
    <main className="space-y-4 p-6">
      <div className="rounded-3xl border border-stone-200 bg-white/60 p-6 shadow-sm">
        <div className="grid gap-4 md:grid-cols-2">
          <DebateCardSkeleton />
          <DebateCardSkeleton />
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <DebateCardSkeleton />
          <DebateCardSkeleton />
        </div>
      </div>
    </main>
  );
}
