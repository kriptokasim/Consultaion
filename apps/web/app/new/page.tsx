"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import RunWorkspaceNew from "@/components/run/RunWorkspaceNew";

function NewWorkspacePage() {
  const searchParams = useSearchParams();
  return <RunWorkspaceNew initialRunId={searchParams.get("run")} />;
}

export default function NewPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-white p-8 font-serif">Loading workspace…</div>}>
      <NewWorkspacePage />
    </Suspense>
  );
}
