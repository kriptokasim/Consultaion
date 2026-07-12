import { describe, it, expect } from "vitest";
import { buildArenaSlots, type ArenaSlot } from "./buildArenaSlots";
import type { PersistedModelResponse } from "@/lib/api/types";
import type { StreamingModelBuffer } from "@/lib/streaming/types";

function makePersisted(overrides: Partial<PersistedModelResponse> & { model_id: string }): PersistedModelResponse {
  const { model_id, ...rest } = overrides;
  return {
    id: rest.id || `resp-${model_id}`,
    debate_id: "debate-1",
    response_type: "arena_response",
    role: "candidate",
    round: 1,
    model_id,
    display_name: rest.display_name || model_id,
    provider: rest.provider || "openai",
    content: rest.content ?? "test content",
    success: rest.success ?? true,
    error_code: null,
    error_message: null,
    retryable: false,
    created_at: null,
    metadata: rest.metadata ?? {},
    ...rest,
  };
}

function makeStream(overrides: Partial<StreamingModelBuffer> & { modelId: string }): StreamingModelBuffer {
  const { modelId, ...rest } = overrides;
  return {
    responseId: rest.responseId || `stream-${modelId}`,
    modelId,
    displayName: rest.displayName || modelId,
    provider: rest.provider || "openai",
    state: rest.state || "streaming",
    accumulatedText: rest.accumulatedText ?? "",
    lastSequence: 0,
    ...rest,
  };
}

describe("buildArenaSlots", () => {
  it("builds slots from panel_config.seats first", () => {
    const seats = [
      { seat_id: "s1", model: "gpt-4o", display_name: "GPT-4o", provider_key: "openai" },
      { seat_id: "s2", model: "claude-3", display_name: "Claude 3", provider_key: "anthropic" },
    ];
    const slots = buildArenaSlots({ panelSeats: seats });
    expect(slots).toHaveLength(2);
    expect(slots[0].modelId).toBe("gpt-4o");
    expect(slots[0].displayName).toBe("GPT-4o");
    expect(slots[1].modelId).toBe("claude-3");
  });

  it("normalizes seat.model_id and seat.seat_id interchangeably", () => {
    const seats = [
      { seat_id: "s1", model_id: "gpt-4o", display_name: "GPT-4o" },
      { seat_id: "s2", display_name: "Gemini" }, // no model, falls back to seat_id
    ];
    const slots = buildArenaSlots({ panelSeats: seats });
    expect(slots[0].modelId).toBe("gpt-4o");
    expect(slots[1].modelId).toBe("s2");
  });

  it("falls back to final_meta.models when no seats", () => {
    const models = [
      { model_id: "gpt-4o", display_name: "GPT-4o", provider: "openai" },
    ];
    const slots = buildArenaSlots({ finalMetaModels: models });
    expect(slots).toHaveLength(1);
    expect(slots[0].modelId).toBe("gpt-4o");
  });

  it("falls back to debate.models", () => {
    const models = ["gpt-4o", "claude-3"];
    const slots = buildArenaSlots({ debateModels: models });
    expect(slots).toHaveLength(2);
    expect(slots[0].modelId).toBe("gpt-4o");
    expect(slots[1].modelId).toBe("claude-3");
  });

  it("uses fallback model IDs when no metadata exists", () => {
    const slots = buildArenaSlots({ fallbackModelIds: ["m1", "m2", "m3"] });
    expect(slots).toHaveLength(3);
    expect(slots[0].modelId).toBe("m1");
    expect(slots[1].modelId).toBe("m2");
    expect(slots[2].modelId).toBe("m3");
  });

  it("does not build slots by iterating persisted responses first", () => {
    const seats = [
      { seat_id: "s1", model: "gpt-4o", display_name: "GPT-4o" },
      { seat_id: "s2", model: "claude-3", display_name: "Claude 3" },
    ];
    const persisted = [
      makePersisted({ model_id: "claude-3", display_name: "Claude 3" }),
      makePersisted({ model_id: "gpt-4o", display_name: "GPT-4o" }),
    ];
    const slots = buildArenaSlots({ panelSeats: seats, persistedResponses: persisted });
    // Slot order should follow seats, not persisted response order
    expect(slots[0].modelId).toBe("gpt-4o");
    expect(slots[1].modelId).toBe("claude-3");
  });

  it("completion-order inversion does not move cards", () => {
    const seats = [
      { seat_id: "s1", model: "model-a", display_name: "Model A" },
      { seat_id: "s2", model: "model-b", display_name: "Model B" },
    ];
    // Model B completed first
    const persisted = [
      makePersisted({ model_id: "model-b", display_name: "Model B" }),
    ];
    const slots = buildArenaSlots({ panelSeats: seats, persistedResponses: persisted });
    expect(slots[0].modelId).toBe("model-a");
    expect(slots[0].type).toBe("placeholder");
    expect(slots[1].modelId).toBe("model-b");
    expect(slots[1].type).toBe("persisted");
  });

  it("appends unexpected responses last", () => {
    const seats = [
      { seat_id: "s1", model: "model-a", display_name: "Model A" },
    ];
    const persisted = [
      makePersisted({ model_id: "model-a", display_name: "Model A" }),
      makePersisted({ model_id: "model-c", display_name: "Model C" }), // unexpected
    ];
    const slots = buildArenaSlots({ panelSeats: seats, persistedResponses: persisted });
    expect(slots).toHaveLength(2);
    expect(slots[0].modelId).toBe("model-a");
    expect(slots[1].modelId).toBe("model-c");
    expect(slots[1].key).toContain("unexpected");
  });

  it("handles failed responses in configured location", () => {
    const seats = [
      { seat_id: "s1", model: "model-a", display_name: "Model A" },
      { seat_id: "s2", model: "model-b", display_name: "Model B" },
    ];
    const persisted = [
      makePersisted({ model_id: "model-a", display_name: "Model A", success: false, content: "" }),
    ];
    const slots = buildArenaSlots({ panelSeats: seats, persistedResponses: persisted });
    expect(slots[0].type).toBe("persisted");
    expect(slots[0].persisted?.success).toBe(false);
    expect(slots[1].type).toBe("placeholder");
  });

  it("streaming card shows as streaming type", () => {
    const seats = [
      { seat_id: "s1", model: "model-a", display_name: "Model A" },
    ];
    const streams = new Map([["model-a", makeStream({ modelId: "model-a", displayName: "Model A", state: "streaming" })]]);
    const slots = buildArenaSlots({ panelSeats: seats, streamingBuffers: streams });
    expect(slots[0].type).toBe("streaming");
    expect(slots[0].streaming?.state).toBe("streaming");
  });

  it("streaming -> persisted transition keeps same position", () => {
    const seats = [
      { seat_id: "s1", model: "model-a", display_name: "Model A" },
      { seat_id: "s2", model: "model-b", display_name: "Model B" },
    ];
    // Model A is persisted, Model B is still streaming
    const persisted = [makePersisted({ model_id: "model-a", display_name: "Model A" })];
    const streams = new Map([["model-b", makeStream({ modelId: "model-b", displayName: "Model B" })]]);
    const slots = buildArenaSlots({ panelSeats: seats, persistedResponses: persisted, streamingBuffers: streams });
    expect(slots[0].type).toBe("persisted");
    expect(slots[0].modelId).toBe("model-a");
    expect(slots[1].type).toBe("streaming");
    expect(slots[1].modelId).toBe("model-b");
  });

  it("no duplicate slot identities", () => {
    const seats = [
      { seat_id: "s1", model: "model-a", display_name: "Model A" },
      { seat_id: "s2", model: "model-a", display_name: "Model A" }, // duplicate
    ];
    const slots = buildArenaSlots({ panelSeats: seats });
    expect(slots).toHaveLength(1);
  });

  it("empty input produces empty slots", () => {
    const slots = buildArenaSlots({});
    expect(slots).toHaveLength(0);
  });

  it("missing panel metadata uses fallback", () => {
    const slots = buildArenaSlots({ fallbackModelIds: ["gpt-4o", "claude-3"] });
    expect(slots).toHaveLength(2);
    expect(slots[0].modelId).toBe("gpt-4o");
  });
});
