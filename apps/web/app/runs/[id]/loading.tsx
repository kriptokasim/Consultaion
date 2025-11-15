"use client";

import LoadingState from "@/components/ui/loading-state";

export default function RunDetailLoading() {
  return (
    <main className="grid place-items-center p-6">
      <LoadingState label="Loading run" description="Fetching debate transcript and judge tallies…" className="max-w-md" />
    </main>
  );
}
