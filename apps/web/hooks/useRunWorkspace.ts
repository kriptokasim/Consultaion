'use client'

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchWithAuth } from "@/lib/auth";
import { getDebate, continueDebate, retryDebate } from "@/lib/api";
import { API_ORIGIN } from "@/lib/config/runtime";
import { useEventSource, type SSEStatus } from "@/lib/sse";
import { normalizeEvent } from "@/lib/api/normalizeEvent";
import type { TimelineEvent } from "@/lib/timeline/types";

export type RunWorkspaceStatus =
  | "idle"
  | "loading"
  | "streaming"
  | "polling"
  | "completed"
  | "failed"
  | "error";

export interface UseRunWorkspaceResult {
  debate: any | null;
  events: TimelineEvent[];
  status: RunWorkspaceStatus;
  sseStatus: SSEStatus;
  error: string | null;
  isPollingFallback: boolean;
  continueRun: () => Promise<void>;
  retryRun: (stageKey?: string) => Promise<void>;
  refetch: () => Promise<void>;
}

export function useRunWorkspace(debateId: string | null): UseRunWorkspaceResult {
  const [debate, setDebate] = useState<any | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPollingFallback, setIsPollingFallback] = useState(false);
  
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isFetchingRef = useRef(false);

  // Determine if debate is in a terminal state
  const isTerminal = debate
    ? ["completed", "success", "completed_budget", "failed"].includes(debate.status)
    : false;

  // 1. Load initial debate & timeline
  const fetchDebateAndTimeline = useCallback(async (id: string) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    try {
      const [debateData, timelineRes] = await Promise.all([
        getDebate(id),
        fetchWithAuth(`/debates/${id}/timeline`),
      ]);

      if (!timelineRes.ok) {
        throw new Error("Failed to fetch timeline");
      }
      
      const timelineData: TimelineEvent[] = await timelineRes.json();
      setDebate(debateData);
      setEvents(timelineData);
      setError(null);
    } catch (err: any) {
      console.error("[useRunWorkspace] Fetch error:", err);
      setError(err?.message || "Failed to load workspace data");
    } finally {
      isFetchingRef.current = false;
    }
  }, []);

  // Initial fetch when debateId changes
  useEffect(() => {
    if (debateId) {
      setIsLoading(true);
      fetchDebateAndTimeline(debateId).finally(() => {
        setIsLoading(false);
      });
    } else {
      setDebate(null);
      setEvents([]);
      setError(null);
      setIsPollingFallback(false);
    }
  }, [debateId, fetchDebateAndTimeline]);

  // 2. Stream Setup (SSE)
  const streamUrl = debateId && !isTerminal ? `${API_ORIGIN}/debates/${debateId}/stream` : null;

  const handleStreamEvent = useCallback((lastEvent: any) => {
    if (!lastEvent || !debateId) return;
    try {
      const normalized = normalizeEvent(lastEvent);
      const newEvent: TimelineEvent = {
        id: lastEvent.id || `sse-${Date.now()}-${Math.random()}`,
        debate_id: debateId,
        ts: lastEvent.ts || new Date().toISOString(),
        type: lastEvent.type,
        round: lastEvent.round || 0,
        seat: lastEvent.seat,
        payload: normalized as unknown as Record<string, unknown>,
      };

      setEvents((prev) => {
        if (prev.some((e) => e.id === newEvent.id)) return prev;
        return [...prev, newEvent];
      });

      // Refetch debate details on key progress events to update workspace metrics
      const eventType = newEvent.type;
      if (
        [
          "arena_response",
          "message",
          "seat_message",
          "model_response",
          "score",
          "stage_checkpoint",
          "final",
          "debate_failed",
        ].includes(eventType)
      ) {
        getDebate(debateId)
          .then((updated) => setDebate(updated))
          .catch((err) => console.error("[useRunWorkspace] Refetch details failed:", err));
      }
    } catch (err) {
      console.error("[useRunWorkspace] Error processing stream event:", err);
    }
  }, [debateId]);

  const { status: sseStatus } = useEventSource<any>(streamUrl, {
    enabled: !!debateId && !isTerminal,
    withCredentials: true,
    parseJson: true,
    onEvent: handleStreamEvent,
  });

  // 3. Fallback Polling Loop
  const startPolling = useCallback((id: string) => {
    if (pollTimerRef.current) return;
    setIsPollingFallback(true);
    console.log("[useRunWorkspace] Starting fallback polling for debate:", id);

    const tick = async () => {
      try {
        await fetchDebateAndTimeline(id);
      } catch (err) {
        console.error("[useRunWorkspace] Polling fetch error:", err);
      }
    };

    pollTimerRef.current = setInterval(tick, 3000);
  }, [fetchDebateAndTimeline]);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setIsPollingFallback(false);
  }, []);

  // Monitor SSE Status & Terminal state to manage polling fallback
  useEffect(() => {
    if (!debateId || isTerminal) {
      stopPolling();
      return;
    }

    if (sseStatus === "closed" || sseStatus === "reconnecting") {
      startPolling(debateId);
    } else if (sseStatus === "connected") {
      stopPolling();
    }
  }, [sseStatus, debateId, isTerminal, startPolling, stopPolling]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, []);

  // 4. Coordinated Workspace Actions
  const handleContinue = useCallback(async () => {
    if (!debateId) return;
    try {
      setError(null);
      await continueDebate(debateId);
      await fetchDebateAndTimeline(debateId);
    } catch (err: any) {
      console.error("[useRunWorkspace] Continue failed:", err);
      setError(err?.message || "Failed to continue debate");
    }
  }, [debateId, fetchDebateAndTimeline]);

  const handleRetry = useCallback(async (stageKey?: string) => {
    if (!debateId) return;
    try {
      setError(null);
      await retryDebate(debateId, stageKey);
      await fetchDebateAndTimeline(debateId);
    } catch (err: any) {
      console.error("[useRunWorkspace] Retry failed:", err);
      setError(err?.message || "Failed to retry stage");
    }
  }, [debateId, fetchDebateAndTimeline]);

  const handleRefetch = useCallback(async () => {
    if (!debateId) return;
    await fetchDebateAndTimeline(debateId);
  }, [debateId, fetchDebateAndTimeline]);

  // Derive unified UI status
  let status: RunWorkspaceStatus = "idle";
  if (isLoading) {
    status = "loading";
  } else if (isTerminal) {
    status = debate?.status === "failed" ? "failed" : "completed";
  } else if (isPollingFallback) {
    status = "polling";
  } else if (sseStatus === "connected" || sseStatus === "connecting" || sseStatus === "reconnecting") {
    status = "streaming";
  } else if (error) {
    status = "error";
  }

  return {
    debate,
    events,
    status,
    sseStatus,
    error,
    isPollingFallback,
    continueRun: handleContinue,
    retryRun: handleRetry,
    refetch: handleRefetch,
  };
}
