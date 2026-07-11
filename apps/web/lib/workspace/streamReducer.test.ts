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
    },
  };
}

describe("streamingReducer buffer bounds", () => {
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
