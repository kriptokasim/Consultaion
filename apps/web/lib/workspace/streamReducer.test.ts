import { describe, expect, test } from "vitest";

import {
  INITIAL_STREAMING_STATE,
  MAX_STREAM_BUFFER_CHARS,
  streamingReducer,
} from "./streamReducer";

function delta(text: string, sequence: number) {
  return {
    type: "RESPONSE_DELTA" as const,
    payload: {
      response_id: "response-1",
      model_id: "model-1",
      display_name: "Model 1",
      provider: "test",
      text,
      delta_sequence: sequence,
      accumulated_chars: text.length,
    },
  };
}

describe("streamingReducer buffer bounds", () => {
  test("does not remove a newer retry buffer when an older response persists", () => {
    const queued = streamingReducer(INITIAL_STREAMING_STATE, {
      type: "RESPONSE_QUEUED",
      payload: { response_id: "response-new", model_id: "model-1" },
    });
    const completed = streamingReducer(queued, {
      type: "RESPONSE_COMPLETED",
      payload: { response_id: "response-new", model_id: "model-1" },
    });
    const merged = streamingReducer(completed, {
      type: "MERGE_PERSISTED",
      payloads: [{
        id: "message-old",
        response_id: "response-old",
        debate_id: "d1",
        response_type: "arena_response",
        role: "arena_response",
        round: 1,
        model_id: "model-1",
        display_name: "Model 1",
        provider: "test",
        content: "old",
        success: true,
        error_code: null,
        error_message: null,
        retryable: false,
        created_at: null,
        metadata: {},
      }],
    });

    expect(merged.buffers.has("response-new")).toBe(true);
  });

  test("applies a delta batch in order and rejects stale sequences", () => {
    const first = delta("hello", 1).payload;
    const stale = delta(" ignored", 1).payload;
    const second = delta(" world", 2).payload;
    const state = streamingReducer(INITIAL_STREAMING_STATE, {
      type: "RESPONSE_DELTA_BATCH",
      payloads: [first, stale, second],
    });

    expect(state.buffers.get("response-1")?.accumulatedText).toBe("hello world");
    expect(state.buffers.get("response-1")?.lastSequence).toBe(2);
  });

  test("does not mark an in-bounds preview as truncated", () => {
    const state = streamingReducer(INITIAL_STREAMING_STATE, delta("hello", 1));

    expect(state.buffers.get("response-1")?.accumulatedText).toBe("hello");
    expect(state.buffers.get("response-1")?.truncated).toBe(false);
  });

  test("caps oversized previews and preserves the truncated state", () => {
    const oversized = "x".repeat(MAX_STREAM_BUFFER_CHARS + 1);
    const capped = streamingReducer(INITIAL_STREAMING_STATE, delta(oversized, 1));
    const next = streamingReducer(capped, delta("more", 2));

    expect(capped.buffers.get("response-1")?.accumulatedText).toHaveLength(
      MAX_STREAM_BUFFER_CHARS,
    );
    expect(capped.buffers.get("response-1")?.truncated).toBe(true);
    expect(next.buffers.get("response-1")?.truncated).toBe(true);
  });
});


describe("streamingReducer lifecycle ordering", () => {
  test("does not regress a streaming response to replayed queued state", () => {
    const streaming = streamingReducer(INITIAL_STREAMING_STATE, delta("hello", 1));
    const replayed = streamingReducer(streaming, {
      type: "RESPONSE_QUEUED",
      payload: { response_id: "response-1", model_id: "model-1" },
    });

    expect(replayed.buffers.get("response-1")?.state).toBe("streaming");
    expect(replayed.buffers.get("response-1")?.accumulatedText).toBe("hello");
  });

  test("reconstructs a completed response when earlier lifecycle events were missed", () => {
    const completed = streamingReducer(INITIAL_STREAMING_STATE, {
      type: "RESPONSE_COMPLETED",
      payload: {
        response_id: "response-late",
        model_id: "model-late",
        display_name: "Late Model",
        provider: "test",
        content: "Late answer survived reconnect",
      },
    });

    expect(completed.buffers.get("response-late")?.state).toBe("completed");
    expect(completed.buffers.get("response-late")?.accumulatedText).toBe(
      "Late answer survived reconnect",
    );
  });

  test("keeps completed state sticky when older lifecycle events replay", () => {
    const streaming = streamingReducer(INITIAL_STREAMING_STATE, delta("done", 1));
    const completed = streamingReducer(streaming, {
      type: "RESPONSE_COMPLETED",
      payload: { response_id: "response-1", model_id: "model-1" },
    });
    const replayed = streamingReducer(completed, {
      type: "RESPONSE_STARTED",
      payload: { response_id: "response-1", model_id: "model-1" },
    });

    expect(replayed.buffers.get("response-1")?.state).toBe("completed");
    expect(replayed.buffers.get("response-1")?.accumulatedText).toBe("done");
  });

  test("does not reopen a completed response when a replayed delta arrives later", () => {
    const completed = streamingReducer(INITIAL_STREAMING_STATE, {
      type: "RESPONSE_COMPLETED",
      payload: {
        response_id: "response-1",
        model_id: "model-1",
        content: "terminal answer",
      },
    });
    const replayed = streamingReducer(completed, delta(" stale tail", 99));

    expect(replayed.buffers.get("response-1")?.state).toBe("completed");
    expect(replayed.buffers.get("response-1")?.accumulatedText).toBe("terminal answer");
  });

  test("does not reopen a failed response when a replayed delta arrives later", () => {
    const failed = streamingReducer(INITIAL_STREAMING_STATE, {
      type: "RESPONSE_FAILED",
      payload: {
        response_id: "response-1",
        model_id: "model-1",
        error: "Provider request timed out.",
        error_code: "model_timeout",
      },
    });
    const replayed = streamingReducer(failed, delta(" stale tail", 99));

    expect(replayed.buffers.get("response-1")?.state).toBe("failed");
    expect(replayed.buffers.get("response-1")?.accumulatedText).toBe("");
  });
});