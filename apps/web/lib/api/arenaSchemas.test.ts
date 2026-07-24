import { describe, expect, it } from "vitest";

import {
  parseArenaBoundaryEvent,
  persistedResponsesSchema,
} from "./arenaSchemas";

describe("Arena boundary schemas", () => {
  it("accepts and flattens the legacy nested final envelope", () => {
    const result = parseArenaBoundaryEvent({
      type: "arena_synthesis",
      payload: {
        content: "Final decision",
        meta: { synthesis_status: "succeeded" },
      },
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.type).toBe("arena_synthesis");
      expect(result.data.content).toBe("Final decision");
    }
  });

  it("rejects an unknown version without throwing", () => {
    const result = parseArenaBoundaryEvent({
      type: "arena_synthesis_revision",
      contract_version: 2,
      synthesis_id: "synth-1",
      run_attempt: 1,
      revision: 0,
      status: "provisional",
      response_ids: ["response-1"],
      successful_count: 1,
      total_count: 2,
      content: "Draft",
    });

    expect(result.success).toBe(false);
  });

  it("rejects malformed terminal payloads", () => {
    const result = parseArenaBoundaryEvent({
      type: "arena_synthesis_finalized",
      contract_version: 1,
      synthesis_id: "synth-1",
      run_attempt: 1,
      revision: 1,
      status: "final",
      response_ids: [],
      successful_count: 1,
      total_count: 2,
    });

    expect(result.success).toBe(false);
  });

  it("accepts streamed final lifecycle boundaries", () => {
    const started = parseArenaBoundaryEvent({
      type: "arena_synthesis_started",
      contract_version: 1,
      synthesis_id: "synth-final",
      run_attempt: 2,
      revision: 1,
      status: "final",
      response_ids: ["response-1", "response-2"],
      successful_count: 2,
      total_count: 2,
    });
    const revision = parseArenaBoundaryEvent({
      type: "arena_synthesis_revision",
      contract_version: 1,
      synthesis_id: "synth-final",
      run_attempt: 2,
      revision: 1,
      status: "final",
      response_ids: ["response-1", "response-2"],
      successful_count: 2,
      total_count: 2,
      content: "Final decision",
    });

    expect(started.success).toBe(true);
    expect(revision.success).toBe(true);
  });

  it("accepts the versioned persisted response boundary", () => {
    const result = persistedResponsesSchema.safeParse({
      contract_version: 1,
      items: [{
        id: "message-1",
        response_id: "response-1",
        debate_id: "debate-1",
        response_type: "arena_response",
        role: "arena_response",
        round: 1,
        model_id: "model-1",
        display_name: "Model 1",
        provider: "test",
        content: "Answer",
        success: true,
        error_code: null,
        error_message: null,
        retryable: false,
        created_at: null,
        metadata: {},
      }],
      summary: {
        expected: 1,
        persisted: 1,
        successful: 1,
        failed: 0,
      },
    });

    expect(result.success).toBe(true);
  });
});
