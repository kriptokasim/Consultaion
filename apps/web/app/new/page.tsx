"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import RunWorkspaceNew from "@/components/run/RunWorkspaceNew";
import { useI18n } from "@/lib/i18n/client";

function NewWorkspacePage() {
  const searchParams = useSearchParams();
  return <RunWorkspaceNew initialRunId={searchParams.get("run")} />;
}

function NewPageFallback() {
  const { t } = useI18n();
  return <div className="min-h-screen bg-white p-8 font-serif">{t("workspace.loading")}</div>;
}

export default function NewPage() {
  return (
    <Suspense fallback={<NewPageFallback />}>
      <NewWorkspacePage />
    </Suspense>
  );
}
