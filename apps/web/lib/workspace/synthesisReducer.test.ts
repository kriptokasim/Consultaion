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

  it("carries verification_status and is_verified through the pipeline", () => {
    const startedState = synthesisReducer(INITIAL_SYNTHESIS_STATE, {
      type: "STARTED",
      payload: { ...started, verification_status: "unverified", is_verified: false, pipeline_type: "structured", report_version: 1 },
    });
    expect(startedState.status).toBe("streaming");
    expect(startedState.verificationStatus).toBe("unverified");
    expect(startedState.isVerified).toBe(false);
    expect(startedState.pipelineType).toBe("structured");
    expect(startedState.reportVersion).toBe(1);

    const finalizedState = synthesisReducer(startedState, {
      type: "FINALIZED",
      payload: {
        ...started,
        revision: 1,
        status: "final",
        content: "Verified final",
        successful_count: 2,
        verification_status: "verified",
        is_verified: true,
        pipeline_type: "structured",
        report_version: 1,
      },
    });
    expect(finalizedState.status).toBe("final");
    expect(finalizedState.verificationStatus).toBe("verified");
    expect(finalizedState.isVerified).toBe(true);
    expect(finalizedState.pipelineType).toBe("structured");
    expect(finalizedState.reportVersion).toBe(1);
  });

  it("preserves fallback text and report on failed final synthesis", () => {
    const provisional = synthesisReducer(INITIAL_SYNTHESIS_STATE, {
      type: "REVISION",
      payload: {
        ...started,
        content: "Provisional text",
        report: { title: "Provisional" },
        verification_status: "unverified",
      },
    });
    expect(provisional.text).toBe("Provisional text");
    expect(provisional.report).toEqual({ title: "Provisional" });

    const failed = synthesisReducer(provisional, {
      type: "FINALIZED",
      payload: {
        ...started,
        revision: 1,
        status: "failed",
        content: "Degraded fallback synthesis content",
        report: { title: "Fallback Report" },
        verification_status: "failed",
      },
    });
    expect(failed.status).toBe("failed");
    expect(failed.text).toBe("Degraded fallback synthesis content");
    expect(failed.report).toEqual({ title: "Fallback Report" });
  });

  it("streams a final revision and rejects late provisional deltas", () => {
    const provisional = synthesisReducer(INITIAL_SYNTHESIS_STATE, {
      type: "DELTA",
      payload: {
        ...started,
        text: "Draft",
        delta_sequence: 1,
      },
    });
    const finalStarted = synthesisReducer(provisional, {
      type: "STARTED",
      payload: {
        ...started,
        synthesis_id: "synth-final",
        revision: 1,
        status: "final",
        response_ids: ["response-a", "response-b"],
        successful_count: 2,
      },
    });
    expect(finalStarted.text).toBe("Draft");
    const finalDelta = synthesisReducer(finalStarted, {
      type: "DELTA",
      payload: {
        ...started,
        synthesis_id: "synth-final",
        revision: 1,
        status: "final",
        response_ids: ["response-a", "response-b"],
        successful_count: 2,
        text: "Definitive",
        delta_sequence: 1,
      },
    });
    const staleDraft = synthesisReducer(finalDelta, {
      type: "DELTA",
      payload: {
        ...started,
        text: " late draft",
        delta_sequence: 2,
      },
    });
    const durableFinal = synthesisReducer(finalDelta, {
      type: "REVISION",
      payload: {
        ...started,
        synthesis_id: "synth-final",
        revision: 1,
        status: "final",
        content: "Definitive decision",
        response_ids: ["response-a", "response-b"],
        successful_count: 2,
      },
    });

    expect(finalDelta.text).toBe("Definitive");
    expect(staleDraft).toBe(finalDelta);
    expect(durableFinal.status).toBe("final");
    expect(durableFinal.text).toBe("Definitive decision");
  });
});


describe("synthesisReducer replay ordering", () => {
  test("duplicate STARTED does not erase visible text", () => {
    const started = synthesisReducer(INITIAL_SYNTHESIS_STATE, {
      type: "STARTED",
      payload: {
        synthesis_id: "s1",
        run_attempt: 1,
        revision: 0,
        status: "provisional",
      },
    });
    const streamed = synthesisReducer(started, {
      type: "DELTA",
      payload: {
        synthesis_id: "s1",
        run_attempt: 1,
        revision: 0,
        status: "provisional",
        text: "visible",
        delta_sequence: 1,
      },
    });
    const replayed = synthesisReducer(streamed, {
      type: "STARTED",
      payload: {
        synthesis_id: "s1",
        run_attempt: 1,
        revision: 0,
        status: "provisional",
      },
    });

    expect(replayed.text).toBe("visible");
    expect(replayed.status).toBe("streaming");
  });

  test("replayed delta does not roll a finalized report back to streaming", () => {
    const finalized = synthesisReducer(INITIAL_SYNTHESIS_STATE, {
      type: "FINALIZED",
      payload: {
        synthesis_id: "s1",
        run_attempt: 1,
        revision: 2,
        status: "final",
        content: "Final decision",
        successful_count: 3,
        total_count: 4,
      },
    });
    expect(finalized.status).toBe("final");

    const replayedDelta = synthesisReducer(finalized, {
      type: "DELTA",
      payload: {
        synthesis_id: "s1",
        run_attempt: 1,
        revision: 2,
        status: "final",
        text: " stale chunk",
        delta_sequence: 5,
      },
    });
    expect(replayedDelta).toBe(finalized);

    const replayedStarted = synthesisReducer(finalized, {
      type: "STARTED",
      payload: {
        synthesis_id: "s1",
        run_attempt: 1,
        revision: 2,
        status: "provisional",
      },
    });
    expect(replayedStarted).toBe(finalized);
  });

  test("replayed delta does not roll a failed report back to streaming", () => {
    const failed = synthesisReducer(INITIAL_SYNTHESIS_STATE, {
      type: "FINALIZED",
      payload: {
        synthesis_id: "s1",
        run_attempt: 1,
        revision: 3,
        status: "failed",
        content: "Fallback content",
      },
    });
    const replayed = synthesisReducer(failed, {
      type: "DELTA",
      payload: {
        synthesis_id: "s1",
        run_attempt: 1,
        revision: 3,
        status: "provisional",
        text: " late",
        delta_sequence: 9,
      },
    });
    expect(replayed).toBe(failed);
  });

  test("a genuinely newer revision supersedes a terminal state", () => {
    const finalized = synthesisReducer(INITIAL_SYNTHESIS_STATE, {
      type: "FINALIZED",
      payload: {
        synthesis_id: "s1",
        run_attempt: 1,
        revision: 2,
        status: "final",
        content: "Final decision",
      },
    });
    const nextRevision = synthesisReducer(finalized, {
      type: "DELTA",
      payload: {
        synthesis_id: "s2",
        run_attempt: 1,
        revision: 3,
        status: "provisional",
        text: "rev3",
        delta_sequence: 1,
      },
    });
    expect(nextRevision.status).toBe("streaming");
    expect(nextRevision.text).toBe("rev3");
  });

  test("same-revision snapshots cannot regress final state", () => {
    const finalized = synthesisReducer(INITIAL_SYNTHESIS_STATE, {
      type: "FINALIZED",
      payload: {
        synthesis_id: "s1",
        run_attempt: 1,
        revision: 2,
        status: "final",
        content: "Final decision",
      },
    });
    const replayed = synthesisReducer(finalized, {
      type: "REVISION",
      payload: {
        synthesis_id: "s1",
        run_attempt: 1,
        revision: 2,
        status: "provisional",
        content: "Late provisional snapshot",
      },
    });

    expect(replayed).toBe(finalized);
  });
});
