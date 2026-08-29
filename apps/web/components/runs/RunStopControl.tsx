"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Square } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { apiRequest, ApiClientError } from "@/lib/apiClient";

const STOPPABLE_STATUSES = new Set([
  "queued",
  "scheduled",
  "running",
  "perspectives_ready",
]);
const TERMINAL_STATUSES = new Set([
  "completed",
  "completed_with_warnings",
  "failed",
  "cancelled",
]);

type RunStatusResponse = {
  id?: string;
  status?: string;
};

type CancelRunResponse = {
  id: string;
  status: "cancelled";
  already_cancelled: boolean;
};

function runIdFromPath(pathname: string | null): string | null {
  if (!pathname) return null;
  const match = pathname.match(/^\/runs\/([^/?#]+)/);
  if (!match?.[1]) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

export function RunStopControl({ enabled = true }: { enabled?: boolean }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runId = useMemo(() => {
    if (!enabled) return null;
    const pathRunId = runIdFromPath(pathname);
    if (pathRunId) return pathRunId;
    if (pathname === "/live") return searchParams.get("run");
    return null;
  }, [enabled, pathname, searchParams]);

  const refreshStatus = useCallback(async () => {
    if (!runId) {
      setStatus(null);
      return;
    }
    try {
      const debate = await apiRequest<RunStatusResponse>({
        method: "GET",
        path: `/debates/${encodeURIComponent(runId)}`,
      });
      setStatus(typeof debate?.status === "string" ? debate.status : null);
      setError(null);
    } catch {
      // This control is supplemental to the Run workspace. Do not turn a
      // temporary status-fetch problem into a page-level failure.
      setStatus(null);
    }
  }, [runId]);

  useEffect(() => {
    setStatus(null);
    setError(null);
    setStopping(false);
    void refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    if (!runId || !status || TERMINAL_STATUSES.has(status)) return;
    const timer = window.setInterval(() => {
      void refreshStatus();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [runId, status, refreshStatus]);

  const stopRun = useCallback(async () => {
    if (!runId || stopping) return;
    const confirmed = window.confirm(
      "Stop this Run? Generated provider usage up to this point will remain recorded.",
    );
    if (!confirmed) return;

    setStopping(true);
    setError(null);
    try {
      const result = await apiRequest<CancelRunResponse>({
        method: "POST",
        path: `/debates/${encodeURIComponent(runId)}/cancel`,
      });
      setStatus(result.status);
      // The backend also publishes a terminal SSE boundary. refresh() is a
      // secondary recovery path for a tab that happened to reconnect exactly
      // while the cancellation event was emitted.
      router.refresh();
    } catch (err) {
      const message =
        err instanceof ApiClientError
          ? err.toUserMessage()
          : "The Run could not be stopped. Please try again.";
      setError(message);
      void refreshStatus();
    } finally {
      setStopping(false);
    }
  }, [refreshStatus, router, runId, stopping]);

  if (!runId || !enabled || status === null) return null;

  if (status === "cancelled") {
    return (
      <div
        className="fixed right-4 z-50 flex min-h-10 items-center gap-2 rounded-full border border-border bg-background/95 px-3 py-2 text-xs font-semibold text-muted-foreground shadow-lg backdrop-blur sm:right-6"
        style={{
          bottom:
            "calc(var(--mobile-bottom-nav-height, 0px) + env(safe-area-inset-bottom) + 1rem)",
        }}
        role="status"
        aria-live="polite"
      >
        <Square className="h-3.5 w-3.5 fill-current" aria-hidden="true" />
        Run stopped
      </div>
    );
  }

  if (!STOPPABLE_STATUSES.has(status)) return null;

  return (
    <div
      className="fixed right-4 z-50 flex max-w-[calc(100vw-2rem)] flex-col items-end gap-2 sm:right-6"
      style={{
        bottom:
          "calc(var(--mobile-bottom-nav-height, 0px) + env(safe-area-inset-bottom) + 1rem)",
      }}
    >
      {error ? (
        <div
          className="max-w-xs rounded-xl border border-destructive/30 bg-background/95 px-3 py-2 text-xs text-destructive shadow-lg backdrop-blur"
          role="alert"
        >
          {error}
        </div>
      ) : null}
      <button
        type="button"
        onClick={stopRun}
        disabled={stopping}
        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-destructive/30 bg-background/95 px-4 py-2 text-sm font-semibold text-destructive shadow-lg backdrop-blur transition hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive/50 disabled:cursor-not-allowed disabled:opacity-60"
        aria-label="Stop Run"
      >
        {stopping ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <Square className="h-3.5 w-3.5 fill-current" aria-hidden="true" />
        )}
        {stopping ? "Stopping…" : "Stop Run"}
      </button>
    </div>
  );
}
