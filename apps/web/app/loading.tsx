"use client";

import { DebateCardSkeleton } from "@/components/ui/skeleton";

export default function RootLoading() {
  return (
    <main className="space-y-4 p-6">
      <DebateCardSkeleton />
      <div className="grid gap-4 md:grid-cols-2">
        <DebateCardSkeleton />
        <DebateCardSkeleton />
      </div>
    </main>
  );
}
