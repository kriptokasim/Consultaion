'use client'

import { useCallback, useEffect, useMemo, useRef, useReducer, useState } from "react";
import { fetchWithAuth } from "@/lib/auth";
import { getDebate, getDebateResponses, continueDebate, retryDebate, resolveContinuationByKey, requestWithTimeout, extractEventItems, TimeoutError, ApiError } from "@/lib/api";
import { API_ORIGIN } from "@/lib/config/runtime";
import { useEventSource, type SSEStatus } from "@/lib/sse";
import { normalizeEvent, normalizeTimelineItems } from "@/lib/api/normalizeEvent";
import type { TimelineEvent } from "@/lib/timeline/types";
import type { PersistedModelResponse } from "@/lib/api/types";
import { streamingReducer, INITIAL_STREAMING_STATE, selectMergedResponses } from "@/lib/workspace/streamReducer";
import type { StreamingState } from "@/lib/workspace/streamReducer";
import { connectionReducer, INITIAL_CONNECTION_STATE } from "@/lib/workspace/connectionReducer";

// ── FH116: Core load failure taxonomy ────────────────────────────────────

export type CoreLoadFailure =
  | "timeout"
  | "not_found"
  | "unauthorized"
  | "forbidden"
  | "server_error"
  | "network_error"
  | "cancelled";

// ── FH117: Decoupled hydration states ────────────────────────────────────

export type CoreState = "idle" | "loading" | "ready" | "failed";

export type ResponsesState =
  | "idle"
  | "loading"
  | "ready"
  | "empty"
  | "failed"
  | "deployment_mismatch";

export type TimelineState = "idle" | "loading" | "ready" | "degraded" | "failed";

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

// ── Continuation intent persistence ──────────────────────────────────────

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
const RESPONSES_TIMEOUT_MS = 8000;

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
  } catch {}
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
  } catch {}
}

// ── FH116: Classify errors into CoreLoadFailure ──────────────────────────

function classifyCoreError(err: any): { code: CoreLoadFailure; httpStatus: number | null } {
  if (err instanceof TimeoutError) {
    return { code: "timeout", httpStatus: null };
  }
  if (err?.name === "AbortError") {
    return { code: "cancelled", httpStatus: null };
  }
  if (err instanceof ApiError) {
    const status = err.status ?? 0;
    switch (status) {
      case 401: return { code: "unauthorized", httpStatus: 401 };
      case 403: return { code: "forbidden", httpStatus: 403 };
      case 404: return { code: "not_found", httpStatus: 404 };
      default:
        if (status >= 500) return { code: "server_error", httpStatus: status };
        return { code: "network_error", httpStatus: status };
    }
  }
  if (err?.message?.includes("Failed to fetch") || err?.message?.includes("NetworkError")) {
    return { code: "network_error", httpStatus: null };
  }
  return { code: "network_error", httpStatus: null };
}

function coreFailureMessage(code: CoreLoadFailure): string {
  switch (code) {
    case "timeout": return "The Run detail request timed out.";
    case "not_found": return "Run not found.";
    case "unauthorized": return "Sign-in required to view this Run.";
    case "forbidden": return "You do not have access to this Run.";
    case "server_error": return "The server could not load this Run.";
    case "network_error": return "The API could not be reached.";
    case "cancelled": return "Request was cancelled.";
  }
}

// ── Timeline hydration ───────────────────────────────────────────────────

type TimelineHydrationResult = {
  events: TimelineEvent[];
  quality: "complete" | "events_fallback" | "debate_only";
  timelineError: string | null;
  eventsError: string | null;
};

async function loadTimelineWithFallback(id: string, signal?: AbortSignal): Promise<TimelineHydrationResult> {
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
}

// ── Hook return type ─────────────────────────────────────────────────────

export interface UseRunWorkspaceResult {
  debate: any | null;
  events: TimelineEvent[];
  responses: PersistedModelResponse[];
  coreState: CoreState;
  responsesState: ResponsesState;
  responsesError: string | null;
  timelineState: TimelineState;
  streamingState: StreamingState;
  mergedStreamingResponses: ReturnType<typeof selectMergedResponses>;
  status: RunWorkspaceStatus;
  sseStatus: SSEStatus;
  error: string | null;
  coreErrorCode: CoreLoadFailure | null;
  coreHttpStatus: number | null;
  outcomeUnknown: boolean;
  isPollingFallback: boolean;
  isSilent: boolean;
  continueRun: () => Promise<void>;
  retryRun: (stageKey?: string) => Promise<void>;
  refetch: () => Promise<void>;
  retryResponses: () => Promise<void>;
  isContinuing: boolean;
  hydrationQuality: RunHydrationQuality;
  timelineError: string | null;
  eventsError: string | null;
}

// ── Main hook ────────────────────────────────────────────────────────────

export function useRunWorkspace(debateId: string | null): UseRunWorkspaceResult {
  const [debate, setDebate] = useState<any | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [connState, dispatchConn] = useReducer(connectionReducer, INITIAL_CONNECTION_STATE);
  const { coreState, responsesState, responsesError, timelineState, coreErrorCode, coreHttpStatus, hydrationQuality, timelineError, eventsError, isPollingFallback } = connState;
    const [isContinuing, setIsContinuing] = useState(false);
  const [outcomeUnknown, setOutcomeUnknown] = useState(false);
        const [responses, setResponses] = useState<PersistedModelResponse[]>([]);

  // FH117: Decoupled states
        
  // FH116: Core error classification
    
  // FH104: Streaming reducer
  const [streamingState, dispatchStreaming] = useReducer(streamingReducer, INITIAL_STREAMING_STATE);

  const mergedStreamingResponses = useMemo(
    () => selectMergedResponses(streamingState),
    [streamingState.buffers, streamingState.persisted],
  );

  // ── FH117: Independent abort controllers ───────────────────────────────
  const coreAbortRef = useRef<AbortController | null>(null);
  const responsesAbortRef = useRef<AbortController | null>(null);
  const timelineAbortRef = useRef<AbortController | null>(null);
  const enrichmentAbortRef = useRef<AbortController | null>(null);

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pollInFlightRef = useRef(false);
  const intentRef = useRef<PersistedContinuationIntent | null>(null);
  const debateSetOnceRef = useRef(false);
  const requestGenerationRef = useRef(0);
  const coreGenerationRef = useRef(0);
  const responsesGenerationRef = useRef(0);
  const timelineGenerationRef = useRef(0);

  // Patchset 132: Silence detection for connected-but-silent streams
  const lastEventTimestampRef = useRef<number>(Date.now());
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [isSilent, setIsSilent] = useState(false);

  // Configurable silence timeout (default 10s)
  const SSE_SILENCE_TIMEOUT_MS = typeof window !== "undefined"
    ? parseInt(process.env.NEXT_PUBLIC_SSE_SILENCE_TIMEOUT_MS || "10000", 10)
    : 10000;
  const SSE_FALLBACK_POLL_MS = typeof window !== "undefined"
    ? parseInt(process.env.NEXT_PUBLIC_SSE_FALLBACK_POLL_MS || "3000", 10)
    : 3000;

  const isTerminal = debate
    ? ["completed", "success", "completed_budget", "failed"].includes(debate.status)
    : false;
  const isPaused = debate?.status === "perspectives_ready";

  // ── FH117: Abort all controllers ───────────────────────────────────────
  const abortAll = useCallback((reason?: string) => {
    [coreAbortRef, responsesAbortRef, timelineAbortRef, enrichmentAbortRef].forEach((ref) => {
      if (ref.current) {
        ref.current.abort(reason || "navigated");
        ref.current = null;
      }
    });
  }, []);

  // ── FH116+FH117: Fetch core debate with timeout and error classification ──
  const fetchCoreDebate = useCallback(async (id: string, signal?: AbortSignal) => {
    const gen = coreGenerationRef.current;
    dispatchConn({ type: "HYDRATION_START" });
    
    

    try {
      const debateData = await getDebate(id, { signal, timeoutMs: DEBATE_TIMEOUT_MS });
      if (gen !== coreGenerationRef.current) return null;

      setDebate(debateData);
      debateSetOnceRef.current = true;
      setError(null);
      dispatchConn({ type: "CORE_LOADED", isTerminal });
      return debateData;
    } catch (err: any) {
      if (gen !== coreGenerationRef.current) return null;

      // Don't show errors for intentional navigation aborts
      if (err?.name === "AbortError" && coreAbortRef.current?.signal?.aborted) {
        dispatchConn({ type: "HYDRATION_START" });
        return null;
      }

      const { code, httpStatus } = classifyCoreError(err);
      dispatchConn({ type: "CORE_FAILED", code, httpStatus, error: err?.message || "Core failed" });
      /* replaced */
      setError(coreFailureMessage(code));
      // handled by CORE_FAILED

      if (!debateSetOnceRef.current) {
        dispatchConn({ type: "TIMELINE_FAILED" });
      }
      return null;
    }
  }, []);

  // ── FH117: Fetch responses independently ───────────────────────────────
  const fetchResponses = useCallback(async (id: string, signal?: AbortSignal) => {
    const gen = responsesGenerationRef.current;
    dispatchConn({ type: "RESPONSES_LOADING" });
    

    try {
      const responsesData = await getDebateResponses(id, { signal, timeoutMs: RESPONSES_TIMEOUT_MS });
      if (gen !== responsesGenerationRef.current) return;

      setResponses(responsesData.items);
      dispatchConn({ type: "RESPONSES_LOADED", count: responsesData.items.length });
      
    } catch (err: any) {
      if (gen !== responsesGenerationRef.current) return;

      // FH119: Distinguish 404 (deployment mismatch) from other failures
      if (err instanceof ApiError && err.status === 404) {
        dispatchConn({ type: "RESPONSES_FAILED", isMismatch: true, error: "Backend contract mismatch — /responses endpoint unavailable" });
        
      } else {
        console.warn("[useRunWorkspace] /responses fetch failed:", err?.message);
        dispatchConn({ type: "RESPONSES_FAILED", isMismatch: false, error: err?.message || "Failed to load persisted responses" });
        
      }
    }
  }, []);

  // ── FH117: Fetch timeline independently ────────────────────────────────
  const fetchTimeline = useCallback(async (id: string, signal?: AbortSignal) => {
    const gen = timelineGenerationRef.current;
    dispatchConn({ type: "TIMELINE_LOADING" });

    try {
      const result = await loadTimelineWithFallback(id, signal);
      if (gen !== timelineGenerationRef.current) return;

      setEvents(result.events);
      dispatchConn({ type: "TIMELINE_LOADED", quality: result.quality, timelineError: result.timelineError, eventsError: result.eventsError });
      
      
      
    } catch (err: any) {
      if (gen !== timelineGenerationRef.current) return;
      console.error("[useRunWorkspace] Timeline fetch error:", err);
      dispatchConn({ type: "TIMELINE_FAILED" });
    }
  }, []);

  // ── FH117: Full hydration — core first, then concurrent enrichment ─────
  const hydrate = useCallback(async (id: string) => {
    const gen = ++requestGenerationRef.current;
    const coreGen = ++coreGenerationRef.current;
    const responsesGen = ++responsesGenerationRef.current;
    const timelineGen = ++timelineGenerationRef.current;

    // Reset all states
    setError(null);
    
    
    
    
    
    
    
    
    debateSetOnceRef.current = false;

    // Abort any in-flight requests
    abortAll("new_hydration");

    // Step 1: Fetch core debate with timeout
    coreAbortRef.current = new AbortController();
    const coreData = await fetchCoreDebate(id, coreAbortRef.current.signal);

    // Patchset 132 Track E: Capture generation locally, check after each await
    if (coreGen !== coreGenerationRef.current) return;
    if (!coreData) return; // Failed or aborted

    // Step 2: Fire responses and timeline concurrently (don't await each other)
    responsesAbortRef.current = new AbortController();
    timelineAbortRef.current = new AbortController();

    void fetchResponses(id, responsesAbortRef.current.signal);
    void fetchTimeline(id, timelineAbortRef.current.signal);
  }, [fetchCoreDebate, fetchResponses, fetchTimeline, abortAll]);

  // ── Retry responses independently ──────────────────────────────────────
  const retryResponses = useCallback(async () => {
    if (!debateId) return;
    if (responsesAbortRef.current) {
      responsesAbortRef.current.abort("retry");
    }
    responsesGenerationRef.current += 1;
    responsesAbortRef.current = new AbortController();
    await fetchResponses(debateId, responsesAbortRef.current.signal);
  }, [debateId, fetchResponses]);

  // ── Main effect: hydrate on debateId change ────────────────────────────
  useEffect(() => {
    if (debateId) {
      hydrate(debateId);
    } else {
      abortAll("cleared");
      requestGenerationRef.current += 1;
      coreGenerationRef.current += 1;
      responsesGenerationRef.current += 1;
      timelineGenerationRef.current += 1;
      setDebate(null);
      setEvents([]);
      setResponses([]);
      dispatchConn({ type: "HYDRATION_START" });
      
      
      
      setError(null);
      
      
      dispatchConn({ type: "STOP_POLLING" });
      setIsContinuing(false);
      
      
      
      debateSetOnceRef.current = false;
    }
  }, [debateId, hydrate, abortAll]);

  // ── Cleanup on unmount ─────────────────────────────────────────────────
  useEffect(() => {
    return () => { abortAll("unmount"); };
  }, [abortAll]);

  // ── SSE stream ─────────────────────────────────────────────────────────
  const streamUrl = debateId && !isTerminal ? `${API_ORIGIN}/debates/${debateId}/stream` : null;

  const handleStreamEvent = useCallback((lastEvent: any) => {
    if (!lastEvent || !debateId) return;
    try {
      const eventType = lastEvent.type;

      // Patchset 132 Track D: Update last event timestamp for silence detection
      lastEventTimestampRef.current = Date.now();
      setIsSilent(false);
      stopPolling();

      // Skip heartbeat events — they only reset the silence timer
      const payloadType = lastEvent.payload?.type;
      if (eventType === "heartbeat" || payloadType === "heartbeat") {
        return;
      }

      // FH104: Dispatch streaming reducer actions
      const STREAMING_EVENT_TYPES = new Set([
        "model_response_queued", "model_response_connecting", "model_response_started",
        "model_response_delta", "model_response_persisting", "model_response_completed",
        "model_response_failed",
      ]);

      if (STREAMING_EVENT_TYPES.has(eventType)) {
        const p = lastEvent.payload || lastEvent;
        switch (eventType) {
          case "model_response_queued": dispatchStreaming({ type: "RESPONSE_QUEUED", payload: p }); break;
          case "model_response_connecting": dispatchStreaming({ type: "RESPONSE_CONNECTING", payload: p }); break;
          case "model_response_started": dispatchStreaming({ type: "RESPONSE_STARTED", payload: p }); break;
          case "model_response_delta": dispatchStreaming({ type: "RESPONSE_DELTA", payload: p }); break;
          case "model_response_persisting": dispatchStreaming({ type: "RESPONSE_PERSISTING", payload: p }); break;
          case "model_response_completed": dispatchStreaming({ type: "RESPONSE_COMPLETED", payload: p }); break;
          case "model_response_failed": dispatchStreaming({ type: "RESPONSE_FAILED", payload: p }); break;
        }
        const newEvent: TimelineEvent = {
          id: lastEvent.id || `sse-${Date.now()}-${Math.random()}`,
          debate_id: debateId, ts: lastEvent.ts || new Date().toISOString(),
          type: eventType, round: lastEvent.round || 0, seat: lastEvent.seat,
          payload: normalizeEvent(lastEvent) as unknown as Record<string, unknown>,
        };
        setEvents((prev) => prev.some((e) => e.id === newEvent.id) ? prev : [...prev, newEvent]);
        return;
      }

      const normalized = normalizeEvent(lastEvent);
      const newEvent: TimelineEvent = {
        id: lastEvent.id || `sse-${Date.now()}-${Math.random()}`,
        debate_id: debateId, ts: lastEvent.ts || new Date().toISOString(),
        type: eventType, round: lastEvent.round || 0, seat: lastEvent.seat,
        payload: normalized as unknown as Record<string, unknown>,
      };
      setEvents((prev) => prev.some((e) => e.id === newEvent.id) ? prev : [...prev, newEvent]);

      // Refetch debate on state-change events
      if (["arena_synthesis", "arena_response", "message", "seat_message", "model_response", "score", "stage_checkpoint", "final", "debate_failed", "perspectives_ready", "debate_completed"].includes(eventType)) {
        getDebate(debateId)
          .then((updated) => setDebate(updated))
          .catch(() => {});
      }

      // Sync persisted responses on terminal events
      if (["arena_synthesis", "debate_completed", "debate_failed", "arena_response"].includes(eventType)) {
        getDebateResponses(debateId)
          .then((data) => {
            setResponses(data.items);
            dispatchConn({ type: "RESPONSES_LOADED", count: data.items.length });
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

  // ── Polling fallback ───────────────────────────────────────────────────
  const startPolling = useCallback((id: string) => {
    if (pollTimerRef.current) return;
    dispatchConn({ type: "START_POLLING" });
    const tick = async () => {
      if (pollInFlightRef.current) {
        pollTimerRef.current = setTimeout(tick, SSE_FALLBACK_POLL_MS) as unknown as NodeJS.Timeout;
        return;
      }
      pollInFlightRef.current = true;
      try {
        await hydrate(id);
      } catch (err) {
        console.error("[useRunWorkspace] Polling fetch error:", err);
      } finally {
        pollInFlightRef.current = false;
        pollTimerRef.current = setTimeout(tick, SSE_FALLBACK_POLL_MS) as unknown as NodeJS.Timeout;
      }
    };
    pollTimerRef.current = setTimeout(tick, SSE_FALLBACK_POLL_MS) as unknown as NodeJS.Timeout;
  }, [hydrate, SSE_FALLBACK_POLL_MS]);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    pollInFlightRef.current = false;
    dispatchConn({ type: "STOP_POLLING" });
  }, []);

  // Patchset 132 Track D: Silence detection — elapsed-time watchdog
  const resetSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) {
      clearInterval(silenceTimerRef.current as unknown as number);
      silenceTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!debateId || isTerminal) {
      stopPolling();
      resetSilenceTimer();
      setIsSilent(false);
      return;
    }

    // Start polling when SSE is closed/reconnecting
    if (sseStatus === "closed" || sseStatus === "reconnecting") {
      startPolling(debateId);
      resetSilenceTimer();
      setIsSilent(false);
      return;
    }

    // When SSE is connected: start elapsed-time watchdog
    if (sseStatus === "connected") {
      stopPolling();
      resetSilenceTimer();
      lastEventTimestampRef.current = Date.now();

      const watchdogTickMs = Math.min(SSE_SILENCE_TIMEOUT_MS / 2, 2000);
      silenceTimerRef.current = setInterval(() => {
        const elapsed = Date.now() - lastEventTimestampRef.current;
        if (elapsed >= SSE_SILENCE_TIMEOUT_MS) {
          setIsSilent(true);
          startPolling(debateId);
        }
      }, watchdogTickMs) as unknown as NodeJS.Timeout;
    }

    return () => {
      resetSilenceTimer();
    };
  }, [sseStatus, debateId, isTerminal, startPolling, stopPolling, resetSilenceTimer, SSE_SILENCE_TIMEOUT_MS]);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    };
  }, []);

  // ── Continuation recovery ──────────────────────────────────────────────
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
            if (res.ok) statusData = await res.json();
          }
          if (!statusData && persisted.idempotencyKey) {
            try { statusData = await resolveContinuationByKey(debateId, persisted.idempotencyKey); } catch {}
          }
          if (statusData) {
            if (statusData.status === "failed" || statusData.status === "cancelled") {
              clearIntent(debateId); intentRef.current = null; idempotencyKeyRef.current = null;
              setIsContinuing(false); setOutcomeUnknown(false);
            } else {
              const updatedIntent: PersistedContinuationIntent = { ...persisted, phase: "tracking", continuationId: statusData.continuation_id || statusData.id, updatedAt: new Date().toISOString() };
              persistIntent(debateId, updatedIntent); intentRef.current = updatedIntent;
              setIsContinuing(true); setOutcomeUnknown(false);
              await hydrate(debateId);
            }
          } else {
            clearIntent(debateId); intentRef.current = null; idempotencyKeyRef.current = null;
            setIsContinuing(false); setOutcomeUnknown(false);
          }
        } catch (err) { console.error("Continuation recovery failed:", err); }
      };
      recover();
    }
  }, [debateId, hydrate]);

  useEffect(() => {
    if (debateId) {
      if (isTerminal) {
        clearIntent(debateId); intentRef.current = null; idempotencyKeyRef.current = null;
        setIsContinuing(false); setOutcomeUnknown(false);
      } else if (isPaused && intentRef.current?.phase === "tracking") {
        clearIntent(debateId); intentRef.current = null; idempotencyKeyRef.current = null;
        setIsContinuing(false); setOutcomeUnknown(false);
      }
    }
  }, [isTerminal, isPaused, debateId]);

  // ── Continue / Retry / Refetch ─────────────────────────────────────────
  const handleContinue = useCallback(async () => {
    if (!debateId) return;
    try {
      setError(null); setIsContinuing(true); setOutcomeUnknown(false);
      if (debate?.continuation_status === "failed" || debate?.continuation_status === "cancelled") {
        idempotencyKeyRef.current = null;
      }
      if (!idempotencyKeyRef.current) idempotencyKeyRef.current = crypto.randomUUID();
      const now = new Date().toISOString();
      const expiresAt = new Date(Date.now() + CONTINUATION_TTL_MS).toISOString();
      const intent: PersistedContinuationIntent = { debateId, idempotencyKey: idempotencyKeyRef.current, createdAt: now, updatedAt: now, phase: "intent_created", expiresAt };
      persistIntent(debateId, intent); intentRef.current = intent;
      const sentIntent = { ...intent, phase: "request_sent" as const, updatedAt: new Date().toISOString() };
      persistIntent(debateId, sentIntent); intentRef.current = sentIntent;
      const retryOfId = (debate?.continuation_status === "failed" || debate?.continuation_status === "cancelled") ? debate.continuation_id : undefined;
      const response = await continueDebate(debateId, idempotencyKeyRef.current, retryOfId);
      const ackIntent = { ...sentIntent, phase: "server_acknowledged" as const, continuationId: response?.continuation_id, updatedAt: new Date().toISOString() };
      persistIntent(debateId, ackIntent); intentRef.current = ackIntent;
      await hydrate(debateId);
      const trackIntent = { ...ackIntent, phase: "tracking" as const, updatedAt: new Date().toISOString() };
      persistIntent(debateId, trackIntent); intentRef.current = trackIntent;
    } catch (err: any) {
      console.error("[useRunWorkspace] Continue failed:", err);
      setError(err?.message || "Failed to continue debate");
      setIsContinuing(false);
      if (intentRef.current?.phase === "request_sent") setOutcomeUnknown(true);
    }
  }, [debateId, debate?.continuation_status, debate?.continuation_id, hydrate]);

  const handleRetry = useCallback(async (stageKey?: string) => {
    if (!debateId) return;
    try {
      setError(null);
      await retryDebate(debateId, stageKey);
      await hydrate(debateId);
    } catch (err: any) {
      console.error("[useRunWorkspace] Retry failed:", err);
      setError(err?.message || "Failed to retry stage");
    }
  }, [debateId, hydrate]);

  const handleRefetch = useCallback(async () => {
    if (!debateId) return;
    await hydrate(debateId);
  }, [debateId, hydrate]);

  // ── Status derivation ──────────────────────────────────────────────────
  const status = connState.status;

  return {
    debate,
    events,
    responses,
    coreState,
    responsesState,
    responsesError,
    timelineState,
    streamingState,
    mergedStreamingResponses,
    status,
    sseStatus,
    error,
    coreErrorCode,
    coreHttpStatus,
    outcomeUnknown,
    isPollingFallback,
    isSilent,
    continueRun: handleContinue,
    retryRun: handleRetry,
    refetch: handleRefetch,
    retryResponses,
    isContinuing,
    hydrationQuality,
    timelineError,
    eventsError,
  };
}
