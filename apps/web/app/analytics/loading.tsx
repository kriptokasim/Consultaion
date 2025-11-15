"use client";

import LoadingState from "@/components/ui/loading-state";

export default function AnalyticsLoading() {
  return (
    <main className="grid place-items-center p-6">
      <LoadingState label="Loading analytics" description="Fetching your debate stats…" className="max-w-sm" />
    </main>
  );
}
