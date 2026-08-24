/**
 * Delta-safe workspace state for streaming model responses.
 *
 * Manages per-response streaming buffers, applies deltas with sequence
 * ordering, and produces the merged response list for rendering.
 *
 * FH104 — no Debate refetch on deltas, reject stale sequences.
 */

import type {
  StreamingModelBuffer,
  ModelState,
  ModelResponseDeltaPayload,
  ModelResponseLifecyclePayload,
} from "../streaming/types";
import { isValidSequence } from "../streaming/types";
import type { PersistedModelResponse } from "../api/types";

// ---------------------------------------------------------------------------
// Buffer bounds
// ---------------------------------------------------------------------------

/** Maximum characters retained in a live streaming preview buffer. */
export const MAX_STREAM_BUFFER_CHARS = 120_000;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

export interface StreamingState {
  /** Active streaming buffers keyed by response_id. */
  buffers: Map<string, StreamingModelBuffer>;
  /** Completed responses merged from persistence. */
  persisted: PersistedModelResponse[];
}

export const INITIAL_STREAMING_STATE: StreamingState = {
  buffers: new Map<string, StreamingModelBuffer>(),
  persisted: [],
};

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

export type StreamingAction =
  | { type: "RESPONSE_QUEUED"; payload: ModelResponseLifecyclePayload }
  | { type: "RESPONSE_CONNECTING"; payload: ModelResponseLifecyclePayload }
  | { type: "RESPONSE_STARTED"; payload: ModelResponseLifecyclePayload }
  | { type: "RESPONSE_DELTA"; payload: ModelResponseDeltaPayload }
  | { type: "RESPONSE_DELTA_BATCH"; payloads: ModelResponseDeltaPayload[] }
  | { type: "RESPONSE_PERSISTING"; payload: { response_id: string } }
  | { type: "RESPONSE_COMPLETED"; payload: ModelResponseLifecyclePayload }
  | { type: "RESPONSE_FAILED"; payload: ModelResponseLifecyclePayload & { error?: string; error_code?: string } }
  | { type: "MERGE_PERSISTED"; payloads: PersistedModelResponse[] }
  | { type: "CLEAR_BUFFER"; response_id: string }
  | { type: "RESET" };

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

const MODEL_STATE_RANK: Record<ModelState, number> = {
  queued: 0,
  connecting: 1,
  started: 2,
  streaming: 3,
  persisting: 4,
  completed: 5,
  failed: 5,
};

function shouldApplyLifecycle(current: ModelState | undefined, incoming: ModelState): boolean {
  if (!current) return true;
  if (current === "completed" || current === "failed") return false;
  return MODEL_STATE_RANK[incoming] >= MODEL_STATE_RANK[current];
}

export function isValidLifecyclePayload(payload: any): payload is ModelResponseLifecyclePayload {
  if (!payload || typeof payload !== "object") return false;
  if (typeof payload.response_id !== "string") return false;
  if (payload.model_id !== undefined && typeof payload.model_id !== "string") return false;
  return true;
}

export function isValidDeltaPayload(payload: any): payload is ModelResponseDeltaPayload {
  if (!payload || typeof payload !== "object") return false;
  if (typeof payload.response_id !== "string") return false;
  if (typeof payload.text !== "string") return false;
  if (typeof payload.delta_sequence !== "number") return false;
  return true;
}

function applyDeltaPayloads(
  state: StreamingState,
  payloads: ModelResponseDeltaPayload[],
): StreamingState {
  let nextBuffers: Map<string, StreamingModelBuffer> | null = null;

  for (const payload of payloads) {
    if (!isValidDeltaPayload(payload)) {
      console.warn("[streamingReducer] Invalid RESPONSE_DELTA payload", payload);
      continue;
    }

    const buffers = nextBuffers ?? state.buffers;
    const { response_id, text, delta_sequence } = payload;
    const buf = buffers.get(response_id) ?? {
      responseId: response_id,
      modelId: payload.model_id || "",
      displayName: (payload as ModelResponseDeltaPayload & { display_name?: string }).display_name || "",
      provider: (payload as ModelResponseDeltaPayload & { provider?: string }).provider || "",
      state: "streaming" as const,
      accumulatedText: "",
      lastSequence: 0,
    };
    // Terminal lifecycle events are authoritative. A reconnect/replay can deliver
    // an older delta after completed/failed; never regress that buffer to streaming.
    if (buf.state === "completed" || buf.state === "failed") continue;
    if (!isValidSequence(delta_sequence, buf.lastSequence)) continue;

    const combined = buf.accumulatedText + text;
    const truncated = combined.length > MAX_STREAM_BUFFER_CHARS;
    const accumulatedText = truncated
      ? combined.slice(0, MAX_STREAM_BUFFER_CHARS)
      : combined;

    if (truncated && !buf.truncated) {
      console.warn(
        `[streamingReducer] Buffer ${response_id} exceeded ${MAX_STREAM_BUFFER_CHARS} chars — truncating preview.`,
      );
    }

    if (!nextBuffers) nextBuffers = new Map(state.buffers);
    nextBuffers.set(response_id, {
      ...buf,
      accumulatedText,
      lastSequence: delta_sequence,
      state: "streaming",
      truncated: Boolean(buf.truncated || truncated),
    });
  }

  return nextBuffers ? { ...state, buffers: nextBuffers } : state;
}

export function streamingReducer(
  state: StreamingState,
  action: StreamingAction,
): StreamingState {
  switch (action.type) {
    case "RESPONSE_QUEUED": {
      if (!isValidLifecyclePayload(action.payload)) {
        console.warn("[streamingReducer] Invalid RESPONSE_QUEUED payload", action.payload);
        return state;
      }
      const { response_id, model_id, display_name, provider } = action.payload;
      const existing = state.buffers.get(response_id);
      if (existing && !shouldApplyLifecycle(existing.state, "queued")) return state;
      const buf: StreamingModelBuffer = {
        responseId: response_id,
        modelId: model_id,
        displayName: display_name,
        provider,
        state: "queued",
        accumulatedText: "",
        lastSequence: 0,
      };
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      next.set(response_id, buf);
      return { ...state, buffers: next };
    }

    case "RESPONSE_CONNECTING": {
      if (!isValidLifecyclePayload(action.payload)) return state;
      const { response_id, model_id, display_name, provider } = action.payload;
      let buf = state.buffers.get(response_id);
      if (buf && !shouldApplyLifecycle(buf.state, "connecting")) return state;
      if (!buf) {
        buf = {
          responseId: response_id,
          modelId: model_id || "",
          displayName: display_name || "",
          provider: provider || "",
          state: "connecting",
          accumulatedText: "",
          lastSequence: 0,
        };
      }
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      next.set(response_id, { ...buf, state: "connecting" });
      return { ...state, buffers: next };
    }

    case "RESPONSE_STARTED": {
      if (!isValidLifecyclePayload(action.payload)) return state;
      const { response_id, model_id, display_name, provider } = action.payload;
      let buf = state.buffers.get(response_id);
      if (buf && !shouldApplyLifecycle(buf.state, "started")) return state;
      if (!buf) {
        buf = {
          responseId: response_id,
          modelId: model_id || "",
          displayName: display_name || "",
          provider: provider || "",
          state: "started",
          accumulatedText: "",
          lastSequence: 0,
        };
      }
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      next.set(response_id, { ...buf, state: "started" });
      return { ...state, buffers: next };
    }

    case "RESPONSE_DELTA": {
      return applyDeltaPayloads(state, [action.payload]);
    }

    case "RESPONSE_DELTA_BATCH": {
      return applyDeltaPayloads(state, action.payloads);
    }

    case "RESPONSE_PERSISTING": {
      if (!action.payload || typeof action.payload.response_id !== "string") return state;
      const buf = state.buffers.get(action.payload.response_id);
      if (!buf || !shouldApplyLifecycle(buf.state, "persisting")) return state;
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      next.set(action.payload.response_id, { ...buf, state: "persisting" });
      return { ...state, buffers: next };
    }

    case "RESPONSE_COMPLETED": {
      if (!isValidLifecyclePayload(action.payload)) return state;
      const { response_id, model_id, display_name, provider, content } = action.payload;
      const buf = state.buffers.get(response_id);
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      if (buf) {
        if (!shouldApplyLifecycle(buf.state, "completed")) return state;
        next.set(response_id, {
          ...buf,
          state: "completed",
          accumulatedText: content || buf.accumulatedText,
        });
      } else {
        // Reconnect may resume at the completed boundary after earlier lifecycle
        // events have fallen out of the transport/replay window.
        next.set(response_id, {
          responseId: response_id,
          modelId: model_id || "",
          displayName: display_name || "",
          provider,
          state: "completed",
          accumulatedText: content || "",
          lastSequence: 0,
        });
      }
      return { ...state, buffers: next };
    }

    case "RESPONSE_FAILED": {
      if (!isValidLifecyclePayload(action.payload)) return state;
      const { response_id, model_id, display_name, provider, error, error_code } = action.payload;
      const buf = state.buffers.get(response_id);
      if (buf) {
        if (!shouldApplyLifecycle(buf.state, "failed")) return state;
        // Existing buffer — mark as failed
        const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
        next.set(response_id, {
          ...buf,
          state: "failed",
          errorCode: error_code,
          errorMessage: error,
        });
        return { ...state, buffers: next };
      }
      // Track G: Create a failed buffer even if queued/started events were missed
      const fallbackBuf: StreamingModelBuffer = {
        responseId: response_id,
        modelId: model_id || "",
        displayName: display_name || "",
        provider,
        state: "failed",
        accumulatedText: "",
        lastSequence: 0,
        errorCode: error_code,
        errorMessage: error,
      };
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      next.set(response_id, fallbackBuf);
      return { ...state, buffers: next };
    }

    case "MERGE_PERSISTED": {
      // Match current responses by their durable stream identity (response_id).
      // Legacy model_id fallback is intentionally removed — matching by model_id
      // alone would incorrectly wipe out a newer retry's streaming buffer when
      // stale persistence rows (pre-response_id) arrive.
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      const persistedIds = new Set(action.payloads.map(p => p.response_id || p.id));
      Array.from(next.entries()).forEach(([key, buf]) => {
        if (persistedIds.has(buf.responseId)) {
          // Only remove if completed or failed — keep active streaming buffers
          if (buf.state === "completed" || buf.state === "failed") {
            next.delete(key);
          }
        }
      });
      return { ...state, buffers: next, persisted: action.payloads };
    }

    case "CLEAR_BUFFER": {
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      next.delete(action.response_id);
      return { ...state, buffers: next };
    }

    case "RESET":
      return INITIAL_STREAMING_STATE;

    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

/** Merge streaming buffers with persisted responses for display. */
export function selectMergedResponses(state: StreamingState): Array<{
  responseId: string;
  modelId: string;
  displayName?: string;
  provider?: string;
  content: string;
  state: ModelState;
  fromStream: boolean;
  errorCode?: string;
  errorMessage?: string;
}> {
  const result: ReturnType<typeof selectMergedResponses> = [];
  const seen = new Set<string>();

  // Active streaming buffers first
  for (const buf of Array.from(state.buffers.values())) {
    seen.add(buf.responseId);
    result.push({
      responseId: buf.responseId,
      modelId: buf.modelId,
      displayName: buf.displayName,
      provider: buf.provider,
      content: buf.accumulatedText,
      state: buf.state,
      fromStream: true,
      errorCode: buf.errorCode,
      errorMessage: buf.errorMessage,
    });
  }

  // Persisted responses (skip if buffer still active)
  for (const p of state.persisted) {
    const responseId = p.response_id || p.id;
    if (!seen.has(responseId)) {
      seen.add(responseId);
      result.push({
        responseId,
        modelId: p.model_id,
        displayName: p.display_name,
        provider: p.provider,
        content: p.content,
        state: p.success ? "completed" : "failed",
        fromStream: false,
      });
    }
  }

  return result;
}