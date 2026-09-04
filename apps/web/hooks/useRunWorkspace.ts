"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useReducer,
  useState,
} from "react";
import { fetchWithAuth } from "@/lib/auth";
import {
  getDebate,
  getDebateResponses,
  continueDebate,
  retryDebate,
  resolveContinuationByKey,
  requestWithTimeout,
  extractEventItems,
  TimeoutError,
  ApiError,
} from "@/lib/api";
import { API_ORIGIN } from "@/lib/config/runtime";
import { useEventSource, type SSEStatus } from "@/lib/sse";
import {
  normalizeEvent,
  normalizeTimelineItems,
} from "@/lib/api/normalizeEvent";
import type { TimelineEvent } from "@/lib/timeline/types";
import type { PersistedModelResponse, DebateDetail } from "@/lib/api/types";
import {
  streamingReducer,
  INITIAL_STREAMING_STATE,
  selectMergedResponses,
} from "@/lib/workspace/streamReducer";
import type { StreamingState } from "@/lib/workspace/streamReducer";
import {
  connectionReducer,
  INITIAL_CONNECTION_STATE,
} from "@/lib/workspace/connectionReducer";
import { isTerminalRunStatus } from "@/lib/runStatus";
import type { ModelResponseDeltaPayload } from "@/lib/streaming/types";
import {
  formatArenaSchemaDiagnostic,
  parseArenaBoundaryEvent,
  parseModelResponseDelta,
  parseSynthesisDelta,
  type ArenaBoundaryEvent,
} from "@/lib/api/arenaSchemas";
import {
  INITIAL_SYNTHESIS_STATE,
  synthesisReducer,
  type SynthesisSnapshotPayload,
  type SynthesisStreamingState,
} from "@/lib/workspace/synthesisReducer";

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
  "idle" | "loading" | "ready" | "empty" | "failed" | "deployment_mismatch";

export type TimelineState =
  "idle" | "loading" | "ready" | "degraded" | "failed";

export type RunWorkspaceStatus =
  | "idle"
  | "loading"
  | "streaming"
  | "polling"
  | "completed"
  | "failed"
  | "error";

export type RunHydrationQuality =
  "complete" | "events_fallback" | "debate_only" | "failed";

// ── Continuation intent persistence ──────────────────────────────────────

export interface PersistedContinuationIntent {
  debateId: string;
  continuationId?: string;
  idempotencyKey: string;
  target?: string;
  createdAt: string;
  updatedAt: string;
  phase: "intent_created" | "request_sent" | "server_acknowledged" | "tracking";
  expiresAt: string;
}

const CONTINUATION_TTL_MS = 24 * 60 * 60 * 1000;
const STORAGE_KEY_PREFIX = "consultaion:continuation";
const DEBATE_TIMEOUT_MS = 12000;
const TIMELINE_TIMEOUT_MS = 6000;
const EVENTS_TIMEOUT_MS = 8000;
const RESPONSES_TIMEOUT_MS = 8000;
const MODEL_RESPONSE_STREAM_EVENT_TYPES = new Set([
  "model_response_queued",
  "model_response_connecting",
  "model_response_started",
  "model_response_delta",
  "model_response_persisting",
  "model_response_completed",
  "model_response_failed",
]);

type SynthesisBoundaryDispatch = {
  action: "STARTED" | "REVISION" | "FINALIZED";
  snapshot: SynthesisSnapshotPayload;
};

function synthesisBoundaryToSnapshot(
  payload: ArenaBoundaryEvent,
  debateId: string,
): SynthesisBoundaryDispatch | null {
  switch (payload.type) {
    case "arena_synthesis_started":
      return {
        action: "STARTED",
        snapshot: {
          synthesis_id: payload.synthesis_id,
          run_attempt: payload.run_attempt,
          revision: payload.revision,
          status: payload.status,
          input_hash: payload.input_hash,
          response_ids: payload.response_ids,
          successful_count: payload.successful_count,
          total_count: payload.total_count,
          verification_status: payload.verification_status,
          is_verified: payload.is_verified,
          pipeline_type: payload.pipeline_type,
          report_version: payload.report_version,
        },
      };
    case "arena_synthesis_revision":
      return {
        action: "REVISION",
        snapshot: {
          synthesis_id: payload.synthesis_id,
          run_attempt: payload.run_attempt,
          revision: payload.revision,
          status: payload.status,
          content: payload.content,
          report: payload.report,
          input_hash: payload.input_hash,
          response_ids: payload.response_ids,
          successful_count: payload.successful_count,
          total_count: payload.total_count,
          verification_status: payload.verification_status,
          is_verified: payload.is_verified,
          pipeline_type: payload.pipeline_type,
          report_version: payload.report_version,
        },
      };
    case "arena_synthesis_finalized":
      return {
        action: "FINALIZED",
        snapshot: {
          synthesis_id: payload.synthesis_id,
          run_attempt: payload.run_attempt,
          revision: payload.revision,
          status: payload.status,
          content: payload.content,
          report: payload.report,
          input_hash: payload.input_hash,
          response_ids: payload.response_ids,
          successful_count: payload.successful_count,
          total_count: payload.total_count,
          provisional_promoted: payload.provisional_promoted,
          verification_status: payload.verification_status,
          is_verified: payload.is_verified,
          pipeline_type: payload.pipeline_type,
          report_version: payload.report_version,
        },
      };
    case "arena_synthesis":
      return {
        action: "FINALIZED",
        snapshot: {
          synthesis_id: payload.synthesis_id || `synth-${debateId}-legacy`,
          run_attempt: payload.run_attempt ?? 0,
          revision: payload.revision ?? 1,
          status: payload.status ?? "final",
          content: payload.content || payload.text || "",
          report: payload.report,
          input_hash: payload.input_hash,
          response_ids: payload.response_ids,
          successful_count: payload.successful_count,
          total_count: payload.total_count,
          provisional_promoted: payload.provisional_promoted,
          verification_status: payload.verification_status,
          is_verified: payload.is_verified,
          pipeline_type: payload.pipeline_type,
          report_version: payload.report_version,
        },
      };
    default:
      return null;
  }
}

function getStorageKey(debateId: string): string {
  return `${STORAGE_KEY_PREFIX}:${debateId}`;
}

function isIntentExpired(intent: PersistedContinuationIntent): boolean {
  return Date.now() > new Date(intent.expiresAt).getTime();
}

function persistIntent(
  debateId: string,
  intent: PersistedContinuationIntent,
): void {
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

function classifyCoreError(err: unknown): {
  code: CoreLoadFailure;
  httpStatus: number | null;
} {
  if (err instanceof TimeoutError) {
    return { code: "timeout", httpStatus: null };
  }
  const errorObj = err instanceof Error ? err : null;
  if (errorObj?.name === "AbortError") {
    return { code: "cancelled", httpStatus: null };
  }
  if (err instanceof ApiError) {
    const status = err.status ?? 0;
    switch (status) {
      case 401:
        return { code: "unauthorized", httpStatus: 401 };
      case 403:
        return { code: "forbidden", httpStatus: 403 };
      case 404:
        return { code: "not_found", httpStatus: 404 };
      default:
        if (status >= 500) return { code: "server_error", httpStatus: status };
        return { code: "network_error", httpStatus: status };
    }
  }
  const fallbackMessage = err instanceof Error ? err.message : String(err);
  if (
    fallbackMessage.includes("Failed to fetch") ||
    fallbackMessage.includes("NetworkError")
  ) {
    return { code: "network_error", httpStatus: null };
  }
  return { code: "network_error", httpStatus: null };
}

function coreFailureMessage(code: CoreLoadFailure): string {
  switch (code) {
    case "timeout":
      return "The Run detail request timed out.";
    case "not_found":
      return "Run not found.";
    case "unauthorized":
      return "Sign-in required to view this Run.";
    case "forbidden":
      return "You do not have access to this Run.";
    case "server_error":
      return "The server could not load this Run.";
    case "network_error":
      return "The API could not be reached.";
    case "cancelled":
      return "Request was cancelled.";
  }
}

// ── Timeline hydration ───────────────────────────────────────────────────

type TimelineHydrationResult = {
  events: TimelineEvent[];
  quality: "complete" | "events_fallback" | "debate_only";
  timelineError: string | null;
  eventsError: string | null;
};

type ResponseRefreshFlight = {
  debateId: string;
  generation: number;
  queued: boolean;
  promise: Promise<void>;
};

async function loadTimelineWithFallback(
  id: string,
  signal?: AbortSignal,
): Promise<TimelineHydrationResult> {
  let timelineEvents: unknown[] | null = null;

  try {
    const data = await requestWithTimeout<unknown>(
      `/debates/${id}/timeline`,
      TIMELINE_TIMEOUT_MS,
      { signal },
    );
    timelineEvents = extractEventItems(data);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.warn(
      "[useRunWorkspace] Timeline failed, falling back to /events:",
      msg,
    );

    try {
      const eventsData = await requestWithTimeout<unknown>(
        `/debates/${id}/events`,
        EVENTS_TIMEOUT_MS,
        { signal },
      );
      timelineEvents = extractEventItems(eventsData);
      const fallbackEvents = normalizeTimelineItems(timelineEvents, id);
      return {
        events: fallbackEvents,
        quality: "events_fallback",
        timelineError: msg,
        eventsError: null,
      };
    } catch (err2: unknown) {
      const msg2 = err2 instanceof Error ? err2.message : String(err2);
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
    const normalized: TimelineEvent[] = normalizeTimelineItems(
      timelineEvents,
      id,
    );
    return {
      events: normalized,
      quality: "complete",
      timelineError: null,
      eventsError: null,
    };
  }
  return {
    events: [],
    quality: "complete",
    timelineError: null,
    eventsError: null,
  };
}

// ── Hook return type ─────────────────────────────────────────────────────

export interface UseRunWorkspaceResult {
  debate: DebateDetail | null;
  events: TimelineEvent[];
  responses: PersistedModelResponse[];
  coreState: CoreState;
  responsesState: ResponsesState;
  responsesError: string | null;
  timelineState: TimelineState;
  streamingState: StreamingState;
  synthesisState: SynthesisStreamingState;
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

let sseEventIdCounter = 0;

export function useRunWorkspace(
  debateId: string | null,
): UseRunWorkspaceResult {
  const [debate, setDebate] = useState<DebateDetail | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [connState, dispatchConn] = useReducer(
    connectionReducer,
    INITIAL_CONNECTION_STATE,
  );
  const {
    coreState,
    responsesState,
    responsesError,
    timelineState,
    coreErrorCode,
    coreHttpStatus,
    hydrationQuality,
    timelineError,
    eventsError,
    isPollingFallback,
  } = connState;
  const [isContinuing, setIsContinuing] = useState(false);
  const [outcomeUnknown, setOutcomeUnknown] = useState(false);
  const [responses, setResponses] = useState<PersistedModelResponse[]>([]);

  // FH117: Decoupled states

  // FH116: Core error classification

  // FH104: Streaming reducer
  const [streamingState, dispatchStreaming] = useReducer(
    streamingReducer,
    INITIAL_STREAMING_STATE,
  );
  const [synthesisState, dispatchSynthesis] = useReducer(
    synthesisReducer,
    INITIAL_SYNTHESIS_STATE,
  );
  const pendingDeltasRef = useRef<ModelResponseDeltaPayload[]>([]);
  const deltaFrameRef = useRef<number | null>(null);

  const flushPendingDeltas = useCallback(() => {
    if (deltaFrameRef.current !== null) {
      cancelAnimationFrame(deltaFrameRef.current);
      deltaFrameRef.current = null;
    }
    if (pendingDeltasRef.current.length === 0) return;

    const payloads = pendingDeltasRef.current;
    pendingDeltasRef.current = [];
    dispatchStreaming({ type: "RESPONSE_DELTA_BATCH", payloads });
  }, []);

  const queueDelta = useCallback(
    (payload: ModelResponseDeltaPayload) => {
      pendingDeltasRef.current.push(payload);
      if (deltaFrameRef.current === null) {
        deltaFrameRef.current = requestAnimationFrame(flushPendingDeltas);
      }
    },
    [flushPendingDeltas],
  );

  const discardPendingDeltas = useCallback(() => {
    if (deltaFrameRef.current !== null) {
      cancelAnimationFrame(deltaFrameRef.current);
      deltaFrameRef.current = null;
    }
    pendingDeltasRef.current = [];
  }, []);

  const mergedStreamingResponses = useMemo(
    () => selectMergedResponses(streamingState),
    [streamingState],
  );

  // ── FH117: Independent abort controllers ───────────────────────────────
  const coreAbortRef = useRef<AbortController | null>(null);
  const responsesAbortRef = useRef<AbortController | null>(null);
  const timelineAbortRef = useRef<AbortController | null>(null);
  const enrichmentAbortRef = useRef<AbortController | null>(null);

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pollInFlightRef = useRef(false);
  const intentRef = useRef<PersistedContinuationIntent | null>(null);
  const idempotencyKeyRef = useRef<string | null>(null);
  const debateSetOnceRef = useRef(false);
  const requestGenerationRef = useRef(0);
  const coreGenerationRef = useRef(0);
  const responsesGenerationRef = useRef(0);
  const timelineGenerationRef = useRef(0);
  const responseRefreshFlightRef = useRef<ResponseRefreshFlight | null>(null);
  const lastRefreshTimeRef = useRef<number>(0);
  const pendingRefreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRefreshArgsRef = useRef<{ id: string; generation: number } | null>(null);
  const MIN_REFRESH_INTERVAL_MS = 2000;
  const activeDebateIdRef = useRef(debateId);
  activeDebateIdRef.current = debateId;

  // Patchset 148 B1: O(1) event dedup via Set instead of O(n) .some()
  const seenEventIdsRef = useRef<Set<string>>(new Set());

  // Track W: performance mark guards
  const firstDeltaMarkedRef = useRef(false);
  const firstCompletedMarkedRef = useRef(false);

  // Patchset 132: Silence detection for connected-but-silent streams
  const lastEventTimestampRef = useRef<number>(Date.now());
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [isSilent, setIsSilent] = useState(false);

  // Configurable silence timeout (default 10s)
  const SSE_SILENCE_TIMEOUT_MS =
    typeof window !== "undefined"
      ? parseInt(process.env.NEXT_PUBLIC_SSE_SILENCE_TIMEOUT_MS || "10000", 10)
      : 10000;
  const SSE_FALLBACK_POLL_MS =
    typeof window !== "undefined"
      ? parseInt(process.env.NEXT_PUBLIC_SSE_FALLBACK_POLL_MS || "3000", 10)
      : 3000;

  // Matches the Retry-After the stream endpoint sends when it refuses a
  // connection, so a refused stream does not fall back to hammering REST.
  const SSE_UNAVAILABLE_POLL_MS = 30000;

  const isTerminal = isTerminalRunStatus(debate?.status);
  const isPaused = debate?.status === "perspectives_ready";

  const isTerminalRef = useRef(isTerminal);
  useEffect(() => {
    isTerminalRef.current = isTerminal;
  }, [isTerminal]);

  // ── FH117: Abort all controllers ───────────────────────────────────────
  const abortAll = useCallback((reason?: string) => {
    [
      coreAbortRef,
      responsesAbortRef,
      timelineAbortRef,
      enrichmentAbortRef,
    ].forEach((ref) => {
      if (ref.current) {
        ref.current.abort(reason || "navigated");
        ref.current = null;
      }
    });
  }, []);

  // ── FH116+FH117: Fetch core debate with timeout and error classification ──
  const fetchCoreDebate = useCallback(
    async (id: string, signal?: AbortSignal) => {
      const gen = coreGenerationRef.current;
      // PS157 Track B: a resolution is stale if the run changed OR a newer
      // request superseded this one. Check both at every completion point.
      const isStale = () =>
        gen !== coreGenerationRef.current || activeDebateIdRef.current !== id;
      dispatchConn({ type: "HYDRATION_START" });

      try {
        const debateData = await getDebate(id, {
          signal,
          timeoutMs: DEBATE_TIMEOUT_MS,
        });
        if (isStale()) return null;

        const isDebateTerminal = isTerminalRunStatus(debateData?.status);

        setDebate(debateData);
        debateSetOnceRef.current = true;
        setError(null);
        dispatchConn({ type: "CORE_LOADED", isTerminal: isDebateTerminal });
        return debateData;
      } catch (err: unknown) {
        if (isStale()) return null;

        const errorObj = err instanceof Error ? err : null;
        if (
          errorObj?.name === "AbortError" &&
          coreAbortRef.current?.signal?.aborted
        ) {
          dispatchConn({ type: "HYDRATION_START" });
          return null;
        }

        const { code, httpStatus } = classifyCoreError(err);
        const message = errorObj?.message || String(err);
        dispatchConn({ type: "CORE_FAILED", code, httpStatus, error: message });
        /* replaced */
        setError(coreFailureMessage(code));
        // handled by CORE_FAILED

        if (!debateSetOnceRef.current) {
          dispatchConn({ type: "TIMELINE_FAILED" });
        }
        return null;
      }
    },
    [],
  );

  // ── FH117: Fetch responses independently ───────────────────────────────
  const fetchResponses = useCallback(
    async (id: string, signal?: AbortSignal) => {
      const gen = responsesGenerationRef.current;
      const isStale = () =>
        gen !== responsesGenerationRef.current ||
        activeDebateIdRef.current !== id;
      dispatchConn({ type: "RESPONSES_LOADING" });

      try {
        const responsesData = await getDebateResponses(
          id,
          { signal, timeoutMs: RESPONSES_TIMEOUT_MS },
          "current",
        );
        if (isStale()) return;

        setResponses(responsesData.items);
        dispatchConn({
          type: "RESPONSES_LOADED",
          count: responsesData.items.length,
        });
        dispatchStreaming({
          type: "MERGE_PERSISTED",
          payloads: responsesData.items,
        });
      } catch (err: unknown) {
        if (isStale()) return;

        // FH119: Distinguish 404 (deployment mismatch) from other failures
        if (err instanceof ApiError && err.status === 404) {
          dispatchConn({
            type: "RESPONSES_FAILED",
            isMismatch: true,
            error:
              "Backend contract mismatch — /responses endpoint unavailable",
          });
        } else {
          const message = err instanceof Error ? err.message : String(err);
          console.warn("[useRunWorkspace] /responses fetch failed:", message);
          dispatchConn({
            type: "RESPONSES_FAILED",
            isMismatch: false,
            error: message,
          });
        }
      }
    },
    [],
  );

  // ── FH117: Fetch timeline independently ────────────────────────────────
  const fetchTimeline = useCallback(
    async (id: string, signal?: AbortSignal) => {
      const gen = timelineGenerationRef.current;
      const isStale = () =>
        gen !== timelineGenerationRef.current ||
        activeDebateIdRef.current !== id;
      dispatchConn({ type: "TIMELINE_LOADING" });

      try {
        const result = await loadTimelineWithFallback(id, signal);
        if (isStale()) return;

        setEvents(result.events);
        for (const event of result.events) {
          const parsed = parseArenaBoundaryEvent({
            ...event.payload,
            type: event.type,
          });
          if (!parsed.success) continue;
          const synthesis = synthesisBoundaryToSnapshot(parsed.data, id);
          if (!synthesis) continue;
          dispatchSynthesis({
            type: synthesis.action,
            payload: synthesis.snapshot,
          });
        }
        dispatchConn({
          type: "TIMELINE_LOADED",
          quality: result.quality,
          timelineError: result.timelineError,
          eventsError: result.eventsError,
        });
      } catch (err: unknown) {
        if (isStale()) return;
        console.error("[useRunWorkspace] Timeline fetch error:", err);
        dispatchConn({ type: "TIMELINE_FAILED" });
      }
    },
    [],
  );

  // ── FH117: Full hydration — core first, then concurrent enrichment ─────
  const hydrate = useCallback(
    async (id: string) => {
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

      // Patchset 132 Track E + PS157 Track B: Capture generation locally, check
      // both generation and active run after each await.
      if (
        coreGen !== coreGenerationRef.current ||
        activeDebateIdRef.current !== id
      )
        return;
      if (!coreData) return; // Failed or aborted

      // Step 2: Fire responses and timeline concurrently (don't await each other)
      responsesAbortRef.current = new AbortController();
      timelineAbortRef.current = new AbortController();

      void fetchResponses(id, responsesAbortRef.current.signal);
      void fetchTimeline(id, timelineAbortRef.current.signal);
    },
    [fetchCoreDebate, fetchResponses, fetchTimeline, abortAll],
  );

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
    // PS157 Track B: A run is an isolation boundary. Tear down ALL async and
    // visible state from the previous run before hydrating the next one, so
    // late work (fetches, SSE events, polls, timers) cannot bleed across.
    abortAll("debate_changed");
    requestGenerationRef.current += 1;
    coreGenerationRef.current += 1;
    responsesGenerationRef.current += 1;
    timelineGenerationRef.current += 1;
    // Visible state
    setDebate(null);
    setEvents([]);
    setResponses([]);
    discardPendingDeltas();
    dispatchStreaming({ type: "RESET" });
    dispatchSynthesis({ type: "RESET" });
    dispatchConn({ type: "RESET_FOR_NEW_RUN" });
    setError(null);
    // Continuation intent (in-memory only; per-run localStorage intents are
    // keyed by debateId and must survive navigation for recovery)
    setIsContinuing(false);
    setOutcomeUnknown(false);
    intentRef.current = null;
    idempotencyKeyRef.current = null;
    debateSetOnceRef.current = false;
    // Event dedup registry (Patchset 148 B1) — cleared before hydrate so no
    // event from the previous run can suppress or leak into the next one.
    seenEventIdsRef.current.clear();
    // Polling fallback
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    pollInFlightRef.current = false;
    dispatchConn({ type: "STOP_POLLING" });
    // Silence watchdog (Patchset 132 Track D)
    if (silenceTimerRef.current) {
      clearInterval(silenceTimerRef.current as unknown as number);
      silenceTimerRef.current = null;
    }
    lastEventTimestampRef.current = Date.now();
    setIsSilent(false);

    if (debateId) {
      void hydrate(debateId);
    }
  }, [debateId, hydrate, abortAll, discardPendingDeltas]);

  // Patchset 148 B1: O(1) append helper
  const appendEventOnce = useCallback((event: TimelineEvent) => {
    setEvents((prev) => {
      if (prev.some(item => item.id === event.id)) return prev;
      return [...prev, event];
    });
  }, []);

  const refreshPersistedResponses = useCallback(
    (id: string, generation: number) => {
      // Cancel any deferred refresh — we'll either run now or re-schedule
      if (pendingRefreshTimerRef.current) {
        clearTimeout(pendingRefreshTimerRef.current);
        pendingRefreshTimerRef.current = null;
      }
      pendingRefreshArgsRef.current = null;

      const now = Date.now();
      const elapsed = now - lastRefreshTimeRef.current;

      // Inside throttle window → schedule a trailing refresh at expiry.
      if (elapsed < MIN_REFRESH_INTERVAL_MS) {
        const remaining = MIN_REFRESH_INTERVAL_MS - elapsed;
        const deferred = new Promise<void>((resolve) => {
          pendingRefreshArgsRef.current = { id, generation };
          pendingRefreshTimerRef.current = setTimeout(() => {
            pendingRefreshTimerRef.current = null;
            pendingRefreshArgsRef.current = null;
            resolve(refreshPersistedResponses(id, generation));
          }, remaining);
        });
        return deferred;
      }

      const current = responseRefreshFlightRef.current;
      if (
        current &&
        current.debateId === id &&
        current.generation === generation
      ) {
        current.queued = true;
        return current.promise;
      }

      const flight: ResponseRefreshFlight = {
        debateId: id,
        generation,
        queued: false,
        promise: Promise.resolve(),
      };
      flight.promise = (async () => {
        try {
          do {
            flight.queued = false;
            const data = await getDebateResponses(id, undefined, "current");
            if (
              activeDebateIdRef.current !== id ||
              requestGenerationRef.current !== generation
            )
              return;

            setResponses(data.items);
            dispatchConn({
              type: "RESPONSES_LOADED",
              count: data.items.length,
            });
            dispatchStreaming({
              type: "MERGE_PERSISTED",
              payloads: data.items,
            });
            lastRefreshTimeRef.current = Date.now();
          } while (flight.queued);
        } catch (err: unknown) {
          if (activeDebateIdRef.current === id) {
            console.warn(
              "[useRunWorkspace] Persisted response refresh failed:",
              err instanceof Error ? err.message : String(err),
            );
          }
        } finally {
          if (responseRefreshFlightRef.current === flight) {
            responseRefreshFlightRef.current = null;
          }
          // After fetch completes, run deferred refresh if one was queued
          // while we were fetching (via the timer path above).
          if (pendingRefreshArgsRef.current) {
            const { id: pendingId, generation: pendingGen } = pendingRefreshArgsRef.current;
            pendingRefreshArgsRef.current = null;
            return refreshPersistedResponses(pendingId, pendingGen);
          }
        }
      })();
      responseRefreshFlightRef.current = flight;
      return flight.promise;
    },
    [],
  );

  // ── Cleanup on unmount ─────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      // PS157 Track B: invalidate every in-flight generation so resolutions
      // arriving after unmount take the stale path instead of setState.
      requestGenerationRef.current += 1;
      coreGenerationRef.current += 1;
      responsesGenerationRef.current += 1;
      timelineGenerationRef.current += 1;
      if (pendingRefreshTimerRef.current) {
        clearTimeout(pendingRefreshTimerRef.current);
        pendingRefreshTimerRef.current = null;
      }
      pendingRefreshArgsRef.current = null;
      discardPendingDeltas();
      abortAll("unmount");
    };
  }, [abortAll, discardPendingDeltas]);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    pollInFlightRef.current = false;
    dispatchConn({ type: "STOP_POLLING" });
  }, []);

  // ── SSE stream ─────────────────────────────────────────────────────────
  const streamUrl =
    debateId && !isTerminal ? `${API_ORIGIN}/debates/${debateId}/stream` : null;

  const handleStreamEvent = useCallback(
    (lastEvent: any) => {
      if (
        !lastEvent ||
        !debateId ||
        activeDebateIdRef.current !== debateId ||
        isTerminalRef.current
      )
        return;
      try {
        const eventType = lastEvent.type;
        const payloadDebateId =
          lastEvent.debate_id || lastEvent.payload?.debate_id;
        if (payloadDebateId && payloadDebateId !== debateId) return;
        const eventGeneration = requestGenerationRef.current;

        // Patchset 132 Track D: Update last event timestamp for silence detection
        lastEventTimestampRef.current = Date.now();
        setIsSilent(false);
        stopPolling();

        // Skip heartbeat events — they only reset the silence timer
        const payloadType = lastEvent.payload?.type;
        if (eventType === "heartbeat" || payloadType === "heartbeat") {
          return;
        }

        if (lastEvent.id && seenEventIdsRef.current.has(lastEvent.id)) return;
        if (lastEvent.id) seenEventIdsRef.current.add(lastEvent.id);

        if (eventType === "arena_synthesis_delta") {
          const parsed = parseSynthesisDelta(lastEvent);
          if (!parsed.success) {
            console.warn(
              `[arena-contract] Invalid synthesis delta dropped: ${formatArenaSchemaDiagnostic(parsed.error)}`,
            );
            return;
          }
          dispatchSynthesis({ type: "DELTA", payload: parsed.data });
          return;
        }

        const isSynthesisBoundary = [
          "arena_synthesis_started",
          "arena_synthesis_revision",
          "arena_synthesis_finalized",
          "arena_synthesis",
        ].includes(eventType);
        const needsArenaBoundaryValidation =
          isSynthesisBoundary ||
          eventType === "arena_started" ||
          (MODEL_RESPONSE_STREAM_EVENT_TYPES.has(eventType) &&
            eventType !== "model_response_delta");
        let validatedBoundary: ArenaBoundaryEvent | undefined;
        if (needsArenaBoundaryValidation) {
          const parsed = parseArenaBoundaryEvent(lastEvent);
          if (!parsed.success) {
            console.warn(
              `[arena-contract] ${eventType} dropped: ${formatArenaSchemaDiagnostic(parsed.error)}`,
            );
            return;
          }
          validatedBoundary = parsed.data;
        }

        // FH104: Dispatch streaming reducer actions
        if (MODEL_RESPONSE_STREAM_EVENT_TYPES.has(eventType)) {
          let p = validatedBoundary ?? lastEvent.payload ?? lastEvent;
          if (eventType === "model_response_delta") {
            const parsed = parseModelResponseDelta(lastEvent);
            if (!parsed.success) {
              console.warn(
                `[arena-contract] Invalid model delta dropped: ${formatArenaSchemaDiagnostic(parsed.error)}`,
              );
              return;
            }
            p = parsed.data;
            firstDeltaMarkedRef.current ||
              (performance.mark?.("sse_first_delta"),
              (firstDeltaMarkedRef.current = true));
            queueDelta(p);
            return;
          }

          // Preserve transport ordering when a lifecycle transition arrives in
          // the same frame as its final content chunks.
          flushPendingDeltas();
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
            case "model_response_persisting":
              dispatchStreaming({ type: "RESPONSE_PERSISTING", payload: p });
              break;
            case "model_response_completed":
              firstCompletedMarkedRef.current ||
                (performance.mark?.("sse_first_completion"),
                (firstCompletedMarkedRef.current = true));
              dispatchStreaming({ type: "RESPONSE_COMPLETED", payload: p });
              break;
            case "model_response_failed":
              dispatchStreaming({ type: "RESPONSE_FAILED", payload: p });
              break;
          }
          if (
            eventType === "model_response_completed" ||
            eventType === "model_response_failed"
          ) {
            void refreshPersistedResponses(debateId, eventGeneration);
          }
          return;
        }

        if (isSynthesisBoundary && validatedBoundary) {
          const synthesis = synthesisBoundaryToSnapshot(
            validatedBoundary,
            debateId,
          );
          if (synthesis?.action === "STARTED") {
            dispatchSynthesis({ type: "STARTED", payload: synthesis.snapshot });
          } else if (synthesis?.action === "REVISION") {
            dispatchSynthesis({
              type: "REVISION",
              payload: synthesis.snapshot,
            });
            performance.mark?.("sse_first_synthesis_visible");
          } else if (synthesis?.action === "FINALIZED") {
            dispatchSynthesis({
              type: "FINALIZED",
              payload: synthesis.snapshot,
            });
            performance.mark?.("sse_report_visible");
          }
        }

        const normalized = normalizeEvent(validatedBoundary ?? lastEvent);
        const normalizedType = validatedBoundary?.type ?? eventType;
        const newEvent: TimelineEvent = {
          id: lastEvent.id || `sse-${Date.now()}-${sseEventIdCounter++}`,
          debate_id: debateId,
          ts: lastEvent.ts || new Date().toISOString(),
          type: normalizedType,
          round: lastEvent.round || 0,
          seat: lastEvent.seat,
          payload: normalized as unknown as Record<string, unknown>,
        };
        appendEventOnce(newEvent);

        // B3: Refetch debate only on low-frequency structural events (not deltas/streaming)
        if (
          [
            "arena_synthesis_finalized",
            "arena_synthesis",
            "debate_failed",
            "perspectives_ready",
            "debate_completed",
            "stage_checkpoint",
            // The rest of the backend's terminal set (sse_backend.TERMINAL_TYPES
            // and sse_terminal_contract). Without these the run never reads as
            // finished, so the client reopens the stream the server just closed.
            "final",
            "error",
            "run_completed",
            "cancelled",
          ].includes(eventType)
        ) {
          if (
            eventType === "arena_synthesis" ||
            eventType === "arena_synthesis_finalized"
          ) {
            performance.mark?.("sse_report_visible");
          }
          getDebate(debateId)
            .then((updated) => {
              if (
                activeDebateIdRef.current === debateId &&
                requestGenerationRef.current === eventGeneration
              ) {
                setDebate(updated);
              }
            })
            .catch(() => {});
        }

        // Sync persisted responses on terminal events
        const isLegacyArenaResponse =
          eventType === "arena_response" &&
          !(lastEvent.payload || lastEvent).response_id;
        if (
          [
            "arena_synthesis_finalized",
            "arena_synthesis",
            "debate_completed",
            "debate_failed",
          ].includes(eventType) ||
          isLegacyArenaResponse
        ) {
          void refreshPersistedResponses(debateId, eventGeneration);
        }
      } catch (err) {
        console.error("[useRunWorkspace] Error processing stream event:", err);
      }
    },
    [
      debateId,
      flushPendingDeltas,
      queueDelta,
      refreshPersistedResponses,
      appendEventOnce,
      stopPolling,
    ],
  );

  const { status: sseStatus } = useEventSource<any>(streamUrl, {
    enabled: !!debateId && !isTerminal,
    withCredentials: true,
    parseJson: true,
    onEvent: handleStreamEvent,
  });

  // ── Polling fallback ───────────────────────────────────────────────────
  const startPolling = useCallback(
    (id: string, intervalMs: number = SSE_FALLBACK_POLL_MS) => {
      if (pollTimerRef.current) return;
      dispatchConn({ type: "START_POLLING" });
      const tick = async () => {
        // PS157 Track B: never run or reschedule a poll for a stale run. The
        // debate-change effect clears pollTimerRef, but a queued/in-flight tick
        // can still fire afterwards — bail before touching shared state.
        if (activeDebateIdRef.current !== id) return;
        if (pollInFlightRef.current) {
          pollTimerRef.current = setTimeout(
            tick,
            SSE_FALLBACK_POLL_MS,
          ) as unknown as NodeJS.Timeout;
          return;
        }
        pollInFlightRef.current = true;
        try {
          await hydrate(id);
        } catch (err) {
          console.error("[useRunWorkspace] Polling fetch error:", err);
        } finally {
          pollInFlightRef.current = false;
          // Only the run that started this poll may continue the loop; if the
          // user switched runs, the new run owns pollTimerRef now.
          if (activeDebateIdRef.current === id) {
            pollTimerRef.current = setTimeout(
              tick,
              intervalMs,
            ) as unknown as NodeJS.Timeout;
          }
        }
      };
      pollTimerRef.current = setTimeout(
        tick,
        intervalMs,
      ) as unknown as NodeJS.Timeout;
    },
    [hydrate, SSE_FALLBACK_POLL_MS],
  );

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

    // The server refused the stream and asked us to back off. Keep the run
    // updated, but at the cadence it requested rather than the fallback rate.
    if (sseStatus === "unavailable") {
      startPolling(debateId, SSE_UNAVAILABLE_POLL_MS);
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
  }, [
    sseStatus,
    debateId,
    isTerminal,
    startPolling,
    stopPolling,
    resetSilenceTimer,
    SSE_SILENCE_TIMEOUT_MS,
  ]);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
      if (silenceTimerRef.current) clearInterval(silenceTimerRef.current);
    };
  }, []);

  // ── Continuation recovery ──────────────────────────────────────────────
  useEffect(() => {
    if (!debateId || typeof window === "undefined") return;
    const persisted = loadIntent(debateId);
    if (persisted) {
      // PS157 Track B: recovery is async — capture the generation so stale
      // resolutions cannot mutate refs/state or hydrate a previous run.
      const recoveryGeneration = requestGenerationRef.current;
      const isStale = () =>
        activeDebateIdRef.current !== debateId ||
        requestGenerationRef.current !== recoveryGeneration;
      intentRef.current = persisted;
      idempotencyKeyRef.current = persisted.idempotencyKey;
      if (
        persisted.phase === "server_acknowledged" ||
        persisted.phase === "tracking" ||
        persisted.phase === "request_sent"
      ) {
        setOutcomeUnknown(true);
        setIsContinuing(true);
      } else {
        setIsContinuing(true);
      }
      const recover = async () => {
        try {
          let statusData = null;
          if (persisted.continuationId) {
            const res = await fetchWithAuth(
              `/debates/${debateId}/continuations/${persisted.continuationId}`,
            );
            if (isStale()) return;
            if (res.ok) statusData = await res.json();
          }
          if (!statusData && persisted.idempotencyKey) {
            try {
              statusData = await resolveContinuationByKey(
                debateId,
                persisted.idempotencyKey,
              );
            } catch {}
          }
          if (isStale()) return;
          if (statusData) {
            if (
              statusData.status === "failed" ||
              statusData.status === "cancelled"
            ) {
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
              await hydrate(debateId);
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
  }, [debateId, hydrate]);

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

  // ── Continue / Retry / Refetch ─────────────────────────────────────────
  const handleContinue = useCallback(async () => {
    if (!debateId) return;
    // PS157 Track B: user may navigate away mid-flight — guard completions.
    const continueGeneration = requestGenerationRef.current;
    const isStale = () =>
      activeDebateIdRef.current !== debateId ||
      requestGenerationRef.current !== continueGeneration;
    try {
      setError(null);
      setIsContinuing(true);
      setOutcomeUnknown(false);
      if (
        debate?.continuation_status === "failed" ||
        debate?.continuation_status === "cancelled"
      ) {
        idempotencyKeyRef.current = null;
      }
      if (!idempotencyKeyRef.current)
        idempotencyKeyRef.current = crypto.randomUUID();
      const now = new Date().toISOString();
      const expiresAt = new Date(
        Date.now() + CONTINUATION_TTL_MS,
      ).toISOString();
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
      const sentIntent = {
        ...intent,
        phase: "request_sent" as const,
        updatedAt: new Date().toISOString(),
      };
      persistIntent(debateId, sentIntent);
      intentRef.current = sentIntent;
      const retryOfId =
        debate?.continuation_status === "failed" ||
        debate?.continuation_status === "cancelled"
          ? debate.continuation_id
          : undefined;
      const response = await continueDebate(
        debateId,
        idempotencyKeyRef.current,
        retryOfId,
      );
      if (isStale()) return;
      const ackIntent = {
        ...sentIntent,
        phase: "server_acknowledged" as const,
        continuationId: response?.continuation_id,
        updatedAt: new Date().toISOString(),
      };
      persistIntent(debateId, ackIntent);
      intentRef.current = ackIntent;
      await hydrate(debateId);
      // hydrate() legitimately bumps the request generation — only the
      // active-run check is meaningful past this point.
      if (activeDebateIdRef.current !== debateId) return;
      const trackIntent = {
        ...ackIntent,
        phase: "tracking" as const,
        updatedAt: new Date().toISOString(),
      };
      persistIntent(debateId, trackIntent);
      intentRef.current = trackIntent;
    } catch (err: unknown) {
      if (activeDebateIdRef.current !== debateId) return;
      const message = err instanceof Error ? err.message : String(err);
      console.error("[useRunWorkspace] Continue failed:", message);
      setError(message);
      setIsContinuing(false);
      if (intentRef.current?.phase === "request_sent") setOutcomeUnknown(true);
    }
  }, [debateId, debate?.continuation_status, debate?.continuation_id, hydrate]);

  const handleRetry = useCallback(
    async (stageKey?: string) => {
      if (!debateId) return;
      // PS157 Track B: user may navigate away mid-flight — guard completions.
      const retryGeneration = requestGenerationRef.current;
      const isStale = () =>
        activeDebateIdRef.current !== debateId ||
        requestGenerationRef.current !== retryGeneration;
      try {
        setError(null);
        await retryDebate(debateId, stageKey);
        if (isStale()) return;
        await hydrate(debateId);
      } catch (err: unknown) {
        if (activeDebateIdRef.current !== debateId) return;
        const message = err instanceof Error ? err.message : String(err);
        console.error("[useRunWorkspace] Retry failed:", message);
        setError(message);
      }
    },
    [debateId, hydrate],
  );

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
    synthesisState,
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
