/**
 * Canonical streaming event types for the Consultaion real-time protocol.
 *
 * Mirrors backend streaming_types.py — keep in sync.
 */

// ---------------------------------------------------------------------------
// Event type enum
// ---------------------------------------------------------------------------

export type StreamEventType =
  | "run_accepted"
  | "run_worker_started"
  | "model_response_queued"
  | "model_response_connecting"
  | "model_response_started"
  | "model_response_delta"
  | "model_response_persisting"
  | "model_response_completed"
  | "model_response_failed"
  | "perspectives_ready"
  | "synthesis_started"
  | "synthesis_completed"
  | "verification_started"
  | "verification_completed"
  | "debate_completed"
  | "debate_failed";

// ---------------------------------------------------------------------------
// Common envelope
// ---------------------------------------------------------------------------

export interface StreamEnvelope {
  id: string;
  type: StreamEventType;
  debate_id: string;
  run_attempt_id?: string | null;
  response_id?: string | null;
  sequence: number;
  timestamp: string;
  payload: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Payload types
// ---------------------------------------------------------------------------

export interface ModelResponseDeltaPayload {
  response_id: string;
  model_id: string;
  text: string;
  delta_sequence: number;
  accumulated_chars: number;
}

export interface ModelResponseLifecyclePayload {
  response_id: string;
  model_id: string;
  display_name?: string;
  provider?: string;
  error?: string;
  error_code?: string;
}

export interface PipelineStagePayload {
  stage: string;
  attempt?: number;
  counts?: {
    responses?: number;
    models_expected?: number;
    scores?: number;
  };
}

// ---------------------------------------------------------------------------
// Streaming state
// ---------------------------------------------------------------------------

export type ModelState =
  | "queued"
  | "connecting"
  | "streaming"
  | "persisting"
  | "completed"
  | "failed";

export interface StreamingModelBuffer {
  responseId: string;
  modelId: string;
  displayName?: string;
  provider?: string;
  state: ModelState;
  accumulatedText: string;
  lastSequence: number;
  errorCode?: string;
  errorMessage?: string;
}

// ---------------------------------------------------------------------------
// Sequence dedup / ordering
// ---------------------------------------------------------------------------

/** Returns true if `incoming` should be accepted (not stale). */
export function isValidSequence(
  incoming: number,
  lastAccepted: number,
): boolean {
  return incoming > lastAccepted;
}

/** Merge a delta into a streaming buffer, rejecting stale sequences. */
export function applyDelta(
  buffer: StreamingModelBuffer,
  delta: ModelResponseDeltaPayload,
): StreamingModelBuffer {
  if (!isValidSequence(delta.delta_sequence, buffer.lastSequence)) {
    return buffer; // stale — ignore
  }
  return {
    ...buffer,
    accumulatedText: buffer.accumulatedText + delta.text,
    lastSequence: delta.delta_sequence,
    state: "streaming",
  };
}
