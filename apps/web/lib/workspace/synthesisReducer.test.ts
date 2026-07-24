import { describe, expect, it } from "vitest";

import {
  INITIAL_SYNTHESIS_STATE,
  synthesisReducer,
} from "./synthesisReducer";

const started = {
  synthesis_id: "synth-1",
  run_attempt: 2,
  revision: 0,
  status: "provisional" as const,
  response_ids: ["response-a"],
  successful_count: 1,
  total_count: 2,
};

describe("synthesisReducer", () => {
  it("streams deltas in sequence and drops replay duplicates", () => {
    const streaming = synthesisReducer(INITIAL_SYNTHESIS_STATE, {
      type: "STARTED",
      payload: started,
    });
    const first = synthesisReducer(streaming, {
      type: "DELTA",
      payload: {
        ...started,
        text: "First",
        delta_sequence: 1,
      },
    });
    const replay = synthesisReducer(first, {
      type: "DELTA",
      payload: {
        ...started,
        text: " duplicate",
        delta_sequence: 1,
      },
    });
    const second = synthesisReducer(replay, {
      type: "DELTA",
      payload: {
        ...started,
        text: " draft",
        delta_sequence: 2,
      },
    });

    expect(replay).toBe(first);
    expect(second.text).toBe("First draft");
    expect(second.lastDeltaSequence).toBe(2);
  });

  it("reconciles a streamed draft with its canonical durable revision", () => {
    const partial = synthesisReducer(INITIAL_SYNTHESIS_STATE, {
      type: "DELTA",
      payload: {
        ...started,
        text: "Partial",
        delta_sequence: 3,
      },
    });
    const durable = synthesisReducer(partial, {
      type: "REVISION",
      payload: {
        ...started,
        content: "Canonical provisional decision",
        report: { title: "Draft" },
      },
    });

    expect(durable.status).toBe("provisional");
    expect(durable.text).toBe("Canonical provisional decision");
    expect(durable.lastDeltaSequence).toBe(0);
  });

  it("converges the same card to final and rejects stale attempts", () => {
    const provisional = synthesisReducer(INITIAL_SYNTHESIS_STATE, {
      type: "REVISION",
      payload: {
        ...started,
        content: "Draft",
      },
    });
    const final = synthesisReducer(provisional, {
      type: "FINALIZED",
      payload: {
        ...started,
        revision: 1,
        status: "final",
        content: "Final",
        response_ids: ["response-a", "response-b"],
        successful_count: 2,
        provisional_promoted: false,
      },
    });
    const stale = synthesisReducer(final, {
      type: "REVISION",
      payload: {
        ...started,
        run_attempt: 1,
        content: "Old worker",
      },
    });

    expect(final.synthesisId).toBe("synth-1");
    expect(final.status).toBe("final");
    expect(final.text).toBe("Final");
    expect(final.responseIds).toEqual(["response-a", "response-b"]);
    expect(stale).toBe(final);
  });
});
