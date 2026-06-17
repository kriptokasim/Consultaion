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
  | { type: "RESPONSE_PERSISTING"; payload: { response_id: string } }
  | { type: "RESPONSE_COMPLETED"; payload: ModelResponseLifecyclePayload }
  | { type: "RESPONSE_FAILED"; payload: ModelResponseLifecyclePayload & { error?: string; error_code?: string } }
  | { type: "MERGE_PERSISTED"; payloads: PersistedModelResponse[] }
  | { type: "CLEAR_BUFFER"; response_id: string }
  | { type: "RESET" };

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

function stateForLifecycle(s: ModelState): ModelState {
  return s;
}

export function streamingReducer(
  state: StreamingState,
  action: StreamingAction,
): StreamingState {
  switch (action.type) {
    case "RESPONSE_QUEUED": {
      const { response_id, model_id, display_name, provider } = action.payload;
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
      const buf = state.buffers.get(action.payload.response_id);
      if (!buf) return state;
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      next.set(action.payload.response_id, { ...buf, state: "connecting" });
      return { ...state, buffers: next };
    }

    case "RESPONSE_STARTED": {
      const buf = state.buffers.get(action.payload.response_id);
      if (!buf) return state;
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      next.set(action.payload.response_id, { ...buf, state: "streaming" });
      return { ...state, buffers: next };
    }

    case "RESPONSE_DELTA": {
      const { response_id, text, delta_sequence } = action.payload;
      const buf = state.buffers.get(response_id);
      if (!buf) return state;
      if (!isValidSequence(delta_sequence, buf.lastSequence)) return state; // stale
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      next.set(response_id, {
        ...buf,
        accumulatedText: buf.accumulatedText + text,
        lastSequence: delta_sequence,
        state: "streaming",
      });
      return { ...state, buffers: next };
    }

    case "RESPONSE_PERSISTING": {
      const buf = state.buffers.get(action.payload.response_id);
      if (!buf) return state;
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      next.set(action.payload.response_id, { ...buf, state: "persisting" });
      return { ...state, buffers: next };
    }

    case "RESPONSE_COMPLETED": {
      const { response_id } = action.payload;
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      next.delete(response_id);
      return { ...state, buffers: next };
    }

    case "RESPONSE_FAILED": {
      const { response_id, error, error_code } = action.payload;
      const buf = state.buffers.get(response_id);
      if (!buf) return state;
      const next = new Map<string, StreamingModelBuffer>(Array.from(state.buffers.entries()));
      next.set(response_id, {
        ...buf,
        state: "failed",
        errorCode: error_code,
        errorMessage: error,
      });
      return { ...state, buffers: next };
    }

    case "MERGE_PERSISTED": {
      return { ...state, persisted: action.payloads };
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
    if (!seen.has(p.id)) {
      seen.add(p.id);
      result.push({
        responseId: p.id,
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
