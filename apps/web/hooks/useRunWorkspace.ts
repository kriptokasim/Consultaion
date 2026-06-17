'use client'

import { useCallback, useEffect, useMemo, useRef, useReducer, useState } from "react";
import { fetchWithAuth } from "@/lib/auth";
import { getDebate, getDebateResponses, continueDebate, retryDebate, resolveContinuationByKey, requestWithTimeout, extractEventItems, TimeoutError, REQUEST_TIMEOUT } from "@/lib/api";
import { API_ORIGIN } from "@/lib/config/runtime";
import { useEventSource, type SSEStatus } from "@/lib/sse";
import { normalizeEvent, normalizeTimelineItems } from "@/lib/api/normalizeEvent";
import type { TimelineEvent } from "@/lib/timeline/types";
import type { PersistedModelResponse, PersistedResponsesResponse } from "@/lib/api/types";
import { streamingReducer, INITIAL_STREAMING_STATE, selectMergedResponses } from "@/lib/workspace/streamReducer";
import type { StreamingState } from "@/lib/workspace/streamReducer";
import type { StreamEnvelope } from "@/lib/streaming/types";

export type RunWorkspaceStatus =
  | "idle"
  | "loading"
  | "streaming"
  | "polling"
  | "completed"
  | "failed"
  | "error";

export type RunHydrationQuality =
  | "complete"
  | "events_fallback"
  | "debate_only"
  | "failed";

export type ResponsesState =
  | "idle"
  | "loading"
  | "ready"
  | "empty"
  | "failed";

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
const DEBATE_TIMEOUT_MS = 12000;
const TIMELINE_TIMEOUT_MS = 6000;
const EVENTS_TIMEOUT_MS = 8000;

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
  }
}

type TimelineHydrationResult = {
  events: TimelineEvent[];
  quality: "complete" | "events_fallback" | "debate_only";
  timelineError: string | null;
  eventsError: string | null;
};

export interface UseRunWorkspaceResult {
  debate: any | null;
  events: TimelineEvent[];
  responses: PersistedModelResponse[];
  responsesState: ResponsesState;
  responsesError: string | null;
  streamingState: StreamingState;
  mergedStreamingResponses: ReturnType<typeof selectMergedResponses>;
  status: RunWorkspaceStatus;
  sseStatus: SSEStatus;
  error: string | null;
  outcomeUnknown: boolean;
  isPollingFallback: boolean;
  continueRun: () => Promise<void>;
  retryRun: (stageKey?: string) => Promise<void>;
  refetch: () => Promise<void>;
  isContinuing: boolean;
  hydrationQuality: RunHydrationQuality;
  timelineError: string | null;
  eventsError: string | null;
}

export function useRunWorkspace(debateId: string | null): UseRunWorkspaceResult {
  const [debate, setDebate] = useState<any | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPollingFallback, setIsPollingFallback] = useState(false);
  const [isContinuing, setIsContinuing] = useState(false);
  const [outcomeUnknown, setOutcomeUnknown] = useState(false);
  const [hydrationQuality, setHydrationQuality] = useState<RunHydrationQuality>("complete");
  const [timelineError, setTimelineError] = useState<string | null>(null);
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [debateSetOnce, setDebateSetOnce] = useState(false);
  const [responses, setResponses] = useState<PersistedModelResponse[]>([]);
  const [responsesState, setResponsesState] = useState<ResponsesState>("idle");
  const [responsesError, setResponsesError] = useState<string | null>(null);
  const [streamingState, dispatchStreaming] = useReducer(streamingReducer, INITIAL_STREAMING_STATE);

  const mergedStreamingResponses = useMemo(
    () => selectMergedResponses(streamingState),
    [streamingState.buffers, streamingState.persisted],
  );

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isFetchingRef = useRef(false);
  const pollInFlightRef = useRef(false);
  const intentRef = useRef<PersistedContinuationIntent | null>(null);
  const debateSetOnceRef = useRef(false);
  const requestGenerationRef = useRef(0);

  const isTerminal = debate
    ? ["completed", "success", "completed_budget", "failed"].includes(debate.status)
    : false;

  const isPaused = debate?.status === "perspectives_ready";

  const loadTimelineWithFallback = useCallback(async (id: string, signal?: AbortSignal): Promise<TimelineHydrationResult> => {
    let timelineEvents: unknown[] | null = null;

    try {
      const data = await requestWithTimeout<unknown>(
        `/debates/${id}/timeline`,
        TIMELINE_TIMEOUT_MS,
        { signal }
      );
      timelineEvents = extractEventItems(data);
    } catch (err: any) {
      const msg = err?.message || "Timeline fetch failed";
      console.warn("[useRunWorkspace] Timeline failed, falling back to /events:", msg);

      try {
        const eventsData = await requestWithTimeout<unknown>(
          `/debates/${id}/events`,
          EVENTS_TIMEOUT_MS,
          { signal }
        );
        timelineEvents = extractEventItems(eventsData);
        const fallbackEvents = normalizeTimelineItems(timelineEvents, id);
        return {
          events: fallbackEvents,
          quality: "events_fallback",
          timelineError: msg,
          eventsError: null,
        };
      } catch (err2: any) {
        const msg2 = err2?.message || "Events fetch failed";
        console.warn("[useRunWorkspace] Both timeline and events failed:", msg2);
        return {
          events: [],
          quality: "debate_only",
          timelineError: msg,
          eventsError: msg2,
        };
      }
    }

    if (timelineEvents && timelineEvents.length > 0) {
      const normalized: TimelineEvent[] = normalizeTimelineItems(timelineEvents, id);
      return { events: normalized, quality: "complete", timelineError: null, eventsError: null };
    }
    return { events: [], quality: "complete", timelineError: null, eventsError: null };
  }, []);

  const fetchDebateOnly = useCallback(async (id: string, signal?: AbortSignal) => {
    const debateData = await getDebate(id, { signal });
    setDebate(debateData);
    setDebateSetOnce(true);
    debateSetOnceRef.current = true;
    setError(null);
    return debateData;
  }, []);

  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchDebateAndTimeline = useCallback(async (id: string) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    const generation = requestGenerationRef.current;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort("navigated");
    }
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

    try {
      // Step 1: Fetch debate core DTO immediately
      const debateData = await fetchDebateOnly(id, signal);

      if (generation !== requestGenerationRef.current) return;

      // Step 2: Fetch canonical /responses (FH90 — first-class response state)
      setResponsesState("loading");
      try {
        const responsesData = await getDebateResponses(id, { signal });
        if (generation !== requestGenerationRef.current) return;
        setResponses(responsesData.items);
        setResponsesState(responsesData.items.length > 0 ? "ready" : "empty");
        setResponsesError(null);
      } catch (respErr: any) {
        if (generation !== requestGenerationRef.current) return;
        console.warn("[useRunWorkspace] /responses fetch failed:", respErr?.message);
        setResponsesState("failed");
        setResponsesError(respErr?.message || "Failed to load persisted responses");
        // Responses failure does not block the rest of hydration
      }

      // Step 3: Fetch timeline as optional enrichment
      const result = await loadTimelineWithFallback(id, signal);

      if (generation !== requestGenerationRef.current) return;

      setEvents(result.events);
      setHydrationQuality(result.quality);
      setTimelineError(result.timelineError);
      setEventsError(result.eventsError);
    } catch (err: any) {
      if (generation !== requestGenerationRef.current) return;
      console.error("[useRunWorkspace] Fetch error:", err);
      setError(err?.message || "Failed to load workspace data");
      if (!debateSetOnceRef.current) {
        setHydrationQuality("failed");
      }
    } finally {
      isFetchingRef.current = false;
    }
  }, [fetchDebateOnly, loadTimelineWithFallback]);

  useEffect(() => {
    if (debateId) {
      requestGenerationRef.current += 1;
      setIsLoading(true);
      setHydrationQuality("complete");
      setTimelineError(null);
      setEventsError(null);
      setResponsesState("idle");
      setResponsesError(null);
      setResponses([]);
      debateSetOnceRef.current = false;
      setDebateSetOnce(false);

      fetchDebateAndTimeline(debateId).finally(() => {
        setIsLoading(false);
      });
    } else {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort("navigated");
        abortControllerRef.current = null;
      }
      requestGenerationRef.current += 1;
      setDebate(null);
      setEvents([]);
      setResponses([]);
      setResponsesState("idle");
      setResponsesError(null);
      setError(null);
      setIsPollingFallback(false);
      setIsContinuing(false);
      setHydrationQuality("complete");
      setTimelineError(null);
      setEventsError(null);
      debateSetOnceRef.current = false;
      setDebateSetOnce(false);
    }
  }, [debateId, fetchDebateAndTimeline]);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort("unmount");
      }
    };
  }, []);

  const streamUrl = debateId && !isTerminal ? `${API_ORIGIN}/debates/${debateId}/stream` : null;

  const handleStreamEvent = useCallback((lastEvent: any) => {
    if (!lastEvent || !debateId) return;
    try {
      const eventType = lastEvent.type;

      // FH104: Dispatch streaming reducer actions for model response lifecycle events
      const STREAMING_EVENT_TYPES = new Set([
        "model_response_queued",
        "model_response_connecting",
        "model_response_started",
        "model_response_delta",
        "model_response_persisting",
        "model_response_completed",
        "model_response_failed",
      ]);

      if (STREAMING_EVENT_TYPES.has(eventType)) {
        const p = lastEvent.payload || lastEvent;
        switch (eventType) {
          case "model_response_queued":
            dispatchStreaming({ type: "RESPONSE_QUEUED", payload: p });
            break;
          case "model_response_connecting":
            dispatchStreaming({ type: "RESPONSE_CONNECTING", payload: p });
            break;
          case "model_response_started":
            dispatchStreaming({ type: "RESPONSE_STARTED", payload: p });
            break;
          case "model_response_delta":
            dispatchStreaming({ type: "RESPONSE_DELTA", payload: p });
            break;
          case "model_response_persisting":
            dispatchStreaming({ type: "RESPONSE_PERSISTING", payload: p });
            break;
          case "model_response_completed":
            dispatchStreaming({ type: "RESPONSE_COMPLETED", payload: p });
            break;
          case "model_response_failed":
            dispatchStreaming({ type: "RESPONSE_FAILED", payload: p });
            break;
        }
        // Also add to events for backward compatibility
        const newEvent: TimelineEvent = {
          id: lastEvent.id || `sse-${Date.now()}-${Math.random()}`,
          debate_id: debateId,
          ts: lastEvent.ts || new Date().toISOString(),
          type: eventType,
          round: lastEvent.round || 0,
          seat: lastEvent.seat,
          payload: normalizeEvent(lastEvent) as unknown as Record<string, unknown>,
        };
        setEvents((prev) => {
          if (prev.some((e) => e.id === newEvent.id)) return prev;
          return [...prev, newEvent];
        });
        return;
      }

      const normalized = normalizeEvent(lastEvent);
      const newEvent: TimelineEvent = {
        id: lastEvent.id || `sse-${Date.now()}-${Math.random()}`,
        debate_id: debateId,
        ts: lastEvent.ts || new Date().toISOString(),
        type: eventType,
        round: lastEvent.round || 0,
        seat: lastEvent.seat,
        payload: normalized as unknown as Record<string, unknown>,
      };

      setEvents((prev) => {
        if (prev.some((e) => e.id === newEvent.id)) return prev;
        return [...prev, newEvent];
      });

      // Refetch debate on terminal/state-change events
      if (
        [
          "arena_response", "message", "seat_message", "model_response",
          "score", "stage_checkpoint", "final", "debate_failed",
          "perspectives_ready", "debate_completed",
        ].includes(eventType)
      ) {
        getDebate(debateId)
          .then((updated) => setDebate(updated))
          .catch((err) => console.error("[useRunWorkspace] Refetch details failed:", err));
      }

      // Sync persisted responses when terminal events arrive
      if (["debate_completed", "debate_failed", "arena_response"].includes(eventType)) {
        getDebateResponses(debateId)
          .then((data) => {
            setResponses(data.items);
            setResponsesState(data.items.length > 0 ? "ready" : "empty");
            dispatchStreaming({ type: "MERGE_PERSISTED", payloads: data.items });
          })
          .catch(() => {});
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
      if (pollInFlightRef.current) {
        pollTimerRef.current = setTimeout(tick, 3000) as unknown as NodeJS.Timeout;
        return;
      }
      pollInFlightRef.current = true;
      try {
        await fetchDebateAndTimeline(id);
      } catch (err) {
        console.error("[useRunWorkspace] Polling fetch error:", err);
      } finally {
        pollInFlightRef.current = false;
        pollTimerRef.current = setTimeout(tick, 3000) as unknown as NodeJS.Timeout;
      }
    };
    pollTimerRef.current = setTimeout(tick, 3000) as unknown as NodeJS.Timeout;
  }, [fetchDebateAndTimeline]);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    pollInFlightRef.current = false;
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
        clearTimeout(pollTimerRef.current);
      }
    };
  }, []);

  const idempotencyKeyRef = useRef<string | null>(null);

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
            }
          }

          if (statusData) {
            if (statusData.status === "failed" || statusData.status === "cancelled") {
              clearIntent(debateId);
              intentRef.current = null;
              idempotencyKeyRef.current = null;
              setIsContinuing(false);
              setOutcomeUnknown(false);
            } else {
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
            clearIntent(debateId);
            intentRef.current = null;
            idempotencyKeyRef.current = null;
            setIsContinuing(false);
            setOutcomeUnknown(false);
          }
        } catch (err) {
          console.error("Continuation recovery failed:", err);
        }
      };

      recover();
    }
  }, [debateId, fetchDebateAndTimeline]);

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

      if (debate?.continuation_status === "failed" || debate?.continuation_status === "cancelled") {
        idempotencyKeyRef.current = null;
      }

      if (!idempotencyKeyRef.current) {
        idempotencyKeyRef.current = crypto.randomUUID();
      }

      const now = new Date().toISOString();
      const expiresAt = new Date(Date.now() + CONTINUATION_TTL_MS).toISOString();

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

      const sentIntent: PersistedContinuationIntent = { ...intent, phase: "request_sent", updatedAt: new Date().toISOString() };
      persistIntent(debateId, sentIntent);
      intentRef.current = sentIntent;

      const retryOfId = (debate?.continuation_status === "failed" || debate?.continuation_status === "cancelled")
        ? debate.continuation_id
        : undefined;

      const response = await continueDebate(debateId, idempotencyKeyRef.current, retryOfId);

      const ackIntent: PersistedContinuationIntent = {
        ...sentIntent,
        phase: "server_acknowledged",
        continuationId: response?.continuation_id,
        updatedAt: new Date().toISOString(),
      };
      persistIntent(debateId, ackIntent);
      intentRef.current = ackIntent;

      await fetchDebateAndTimeline(debateId);

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
    responses,
    responsesState,
    responsesError,
    streamingState,
    mergedStreamingResponses,
    status,
    sseStatus,
    error,
    outcomeUnknown,
    isPollingFallback,
    continueRun: handleContinue,
    retryRun: handleRetry,
    refetch: handleRefetch,
    isContinuing,
    hydrationQuality,
    timelineError,
    eventsError,
  };
}
