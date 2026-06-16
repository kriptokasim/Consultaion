'use client'

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchWithAuth } from "@/lib/auth";
import { getDebate, continueDebate, retryDebate, resolveContinuationByKey } from "@/lib/api";
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

export interface PersistedContinuationIntent {
  debateId: string;
  continuationId?: string;
  idempotencyKey: string;
  target?: string;
  createdAt: string;
  updatedAt: string;
  phase:
    | "intent_created"
    | "request_sent"
    | "server_acknowledged"
    | "tracking";
  expiresAt: string;
}

const CONTINUATION_TTL_MS = 24 * 60 * 60 * 1000;
const STORAGE_KEY_PREFIX = "consultaion:continuation";

function getStorageKey(debateId: string): string {
  return `${STORAGE_KEY_PREFIX}:${debateId}`;
}

function isIntentExpired(intent: PersistedContinuationIntent): boolean {
  return Date.now() > new Date(intent.expiresAt).getTime();
}

function persistIntent(debateId: string, intent: PersistedContinuationIntent): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(getStorageKey(debateId), JSON.stringify(intent));
  } catch {
    // non-critical
  }
}

function loadIntent(debateId: string): PersistedContinuationIntent | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(getStorageKey(debateId));
    if (!raw) return null;
    const parsed: PersistedContinuationIntent = JSON.parse(raw);
    if (isIntentExpired(parsed)) {
      localStorage.removeItem(getStorageKey(debateId));
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function clearIntent(debateId: string): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(getStorageKey(debateId));
  } catch {
    // non-critical
  }
}

export interface UseRunWorkspaceResult {
  debate: any | null;
  events: TimelineEvent[];
  status: RunWorkspaceStatus;
  sseStatus: SSEStatus;
  error: string | null;
  outcomeUnknown: boolean;
  isPollingFallback: boolean;
  continueRun: () => Promise<void>;
  retryRun: (stageKey?: string) => Promise<void>;
  refetch: () => Promise<void>;
  isContinuing: boolean;
}

export function useRunWorkspace(debateId: string | null): UseRunWorkspaceResult {
  const [debate, setDebate] = useState<any | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPollingFallback, setIsPollingFallback] = useState(false);
  const [isContinuing, setIsContinuing] = useState(false);
  const [outcomeUnknown, setOutcomeUnknown] = useState(false);

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isFetchingRef = useRef(false);
  const intentRef = useRef<PersistedContinuationIntent | null>(null);

  const isTerminal = debate
    ? ["completed", "success", "completed_budget", "failed"].includes(debate.status)
    : false;

  const isPaused = debate?.status === "perspectives_ready";

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
      setIsContinuing(false);
    }
  }, [debateId, fetchDebateAndTimeline]);

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

      const eventType = newEvent.type;
      if (
        [
          "arena_response", "message", "seat_message", "model_response",
          "score", "stage_checkpoint", "final", "debate_failed",
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

  const startPolling = useCallback((id: string) => {
    if (pollTimerRef.current) return;
    setIsPollingFallback(true);
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

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, []);

  const idempotencyKeyRef = useRef<string | null>(null);

  // Restore persisted intent on mount / debateId change
  useEffect(() => {
    if (!debateId || typeof window === "undefined") return;

    const persisted = loadIntent(debateId);
    if (persisted) {
      intentRef.current = persisted;
      idempotencyKeyRef.current = persisted.idempotencyKey;

      if (persisted.phase === "server_acknowledged" || persisted.phase === "tracking" || persisted.phase === "request_sent") {
        setOutcomeUnknown(true);
        setIsContinuing(true);
      } else {
        setIsContinuing(true);
      }

      // Invoke recovery procedure
      const recover = async () => {
        try {
          let statusData = null;
          if (persisted.continuationId) {
            const res = await fetchWithAuth(`/debates/${debateId}/continuations/${persisted.continuationId}`);
            if (res.ok) {
              statusData = await res.json();
            }
          }
          if (!statusData && persisted.idempotencyKey) {
            try {
              statusData = await resolveContinuationByKey(debateId, persisted.idempotencyKey);
            } catch {
              // ignore error
            }
          }

          if (statusData) {
            if (statusData.status === "failed" || statusData.status === "cancelled") {
              // Clean up the storage intent, update status, and enable retrying.
              clearIntent(debateId);
              intentRef.current = null;
              idempotencyKeyRef.current = null;
              setIsContinuing(false);
              setOutcomeUnknown(false);
            } else {
              // Succeeded or in progress, update intent to tracking and keep polling/syncing
              const updatedIntent: PersistedContinuationIntent = {
                ...persisted,
                phase: "tracking",
                continuationId: statusData.continuation_id || statusData.id,
                updatedAt: new Date().toISOString(),
              };
              persistIntent(debateId, updatedIntent);
              intentRef.current = updatedIntent;
              setIsContinuing(true);
              setOutcomeUnknown(false);
              await fetchDebateAndTimeline(debateId);
            }
          } else {
            // No info, clean up
            clearIntent(debateId);
            intentRef.current = null;
            idempotencyKeyRef.current = null;
            setIsContinuing(false);
            setOutcomeUnknown(false);
          }
        } catch (err) {
          console.error("Continuation recovery failed:", err);
          // If transient error, keep states as is to let polling/user retry
        }
      };

      recover();
    }
  }, [debateId, fetchDebateAndTimeline]);

  // Clear intent ONLY on terminal or confirmed paused
  useEffect(() => {
    if (debateId) {
      if (isTerminal) {
        clearIntent(debateId);
        intentRef.current = null;
        idempotencyKeyRef.current = null;
        setIsContinuing(false);
        setOutcomeUnknown(false);
      } else if (isPaused && intentRef.current?.phase === "tracking") {
        clearIntent(debateId);
        intentRef.current = null;
        idempotencyKeyRef.current = null;
        setIsContinuing(false);
        setOutcomeUnknown(false);
      }
    }
  }, [isTerminal, isPaused, debateId]);

  const handleContinue = useCallback(async () => {
    if (!debateId) return;
    try {
      setError(null);
      setIsContinuing(true);
      setOutcomeUnknown(false);

      // If previous continuation failed/cancelled, clear key to force a new one
      if (debate?.continuation_status === "failed" || debate?.continuation_status === "cancelled") {
        idempotencyKeyRef.current = null;
      }

      if (!idempotencyKeyRef.current) {
        idempotencyKeyRef.current = crypto.randomUUID();
      }

      const now = new Date().toISOString();
      const expiresAt = new Date(Date.now() + CONTINUATION_TTL_MS).toISOString();

      // Phase: intent_created
      const intent: PersistedContinuationIntent = {
        debateId,
        idempotencyKey: idempotencyKeyRef.current,
        createdAt: now,
        updatedAt: now,
        phase: "intent_created",
        expiresAt,
      };
      persistIntent(debateId, intent);
      intentRef.current = intent;

      // Phase: request_sent
      const sentIntent: PersistedContinuationIntent = { ...intent, phase: "request_sent", updatedAt: new Date().toISOString() };
      persistIntent(debateId, sentIntent);
      intentRef.current = sentIntent;

      const retryOfId = (debate?.continuation_status === "failed" || debate?.continuation_status === "cancelled")
        ? debate.continuation_id
        : undefined;

      const response = await continueDebate(debateId, idempotencyKeyRef.current, retryOfId);

      // Phase: server_acknowledged — store continuationId
      const ackIntent: PersistedContinuationIntent = {
        ...sentIntent,
        phase: "server_acknowledged",
        continuationId: response?.continuation_id,
        updatedAt: new Date().toISOString(),
      };
      persistIntent(debateId, ackIntent);
      intentRef.current = ackIntent;

      await fetchDebateAndTimeline(debateId);

      // Phase: tracking — intent stays until terminal
      const trackIntent: PersistedContinuationIntent = {
        ...ackIntent,
        phase: "tracking",
        updatedAt: new Date().toISOString(),
      };
      persistIntent(debateId, trackIntent);
      intentRef.current = trackIntent;
    } catch (err: any) {
      console.error("[useRunWorkspace] Continue failed:", err);
      setError(err?.message || "Failed to continue debate");
      setIsContinuing(false);
      // Keep outcomeUnknown if POST might have been accepted
      if (intentRef.current?.phase === "request_sent") {
        setOutcomeUnknown(true);
      }
    }
  }, [debateId, debate?.continuation_status, debate?.continuation_id, fetchDebateAndTimeline]);

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
    outcomeUnknown,
    isPollingFallback,
    continueRun: handleContinue,
    retryRun: handleRetry,
    refetch: handleRefetch,
    isContinuing,
  };
}
