import { describe, it, expect } from "vitest";
import {
  normalizeSSEEnvelope,
  isTerminalEvent,
  isErrorEvent,
  isHeartbeatEvent,
  assertEventTypeExhaustive,
} from "./eventContract";

describe("normalizeSSEEnvelope", () => {
  it("normalizes envelope with payload", () => {
    const event = normalizeSSEEnvelope({
      sequence: 1,
      type: "message",
      payload: {
        type: "message",
        role: "agent",
        agent_name: "model-a",
        content: "Hello",
      },
    });
    expect(event).toEqual({
      type: "message",
      role: "agent",
      agent_name: "model-a",
      content: "Hello",
    });
  });

  it("normalizes flat event object", () => {
    const event = normalizeSSEEnvelope({
      type: "heartbeat",
    });
    expect(event).toEqual({ type: "heartbeat" });
  });

  it("returns null for unknown event type", () => {
    const event = normalizeSSEEnvelope({ type: "unknown_type", data: {} });
    expect(event).toBeNull();
  });

  it("returns null for non-object input", () => {
    expect(normalizeSSEEnvelope(null)).toBeNull();
    expect(normalizeSSEEnvelope("string")).toBeNull();
    expect(normalizeSSEEnvelope(42)).toBeNull();
  });

  it("handles score events", () => {
    const event = normalizeSSEEnvelope({
      type: "score",
      agent_name: "model-a",
      criterion: "coherence",
      value: 0.85,
    });
    expect(event?.type).toBe("score");
  });

  it("handles final events", () => {
    const event = normalizeSSEEnvelope({
      type: "final",
      summary: "Debate complete",
      winner: "model-a",
    });
    expect(event?.type).toBe("final");
  });

  it("handles error events", () => {
    const event = normalizeSSEEnvelope({
      type: "error",
      message: "Something went wrong",
      retryable: true,
    });
    expect(event?.type).toBe("error");
  });
});

describe("isTerminalEvent", () => {
  it("returns true for final event", () => {
    expect(isTerminalEvent({ type: "final" })).toBe(true);
  });

  it("returns false for other events", () => {
    expect(isTerminalEvent({ type: "message", role: "agent", agent_name: "", content: "" })).toBe(false);
  });
});

describe("isErrorEvent", () => {
  it("returns true for error event", () => {
    expect(isErrorEvent({ type: "error", message: "fail" })).toBe(true);
  });

  it("returns false for non-error event", () => {
    expect(isErrorEvent({ type: "heartbeat" })).toBe(false);
  });
});

describe("isHeartbeatEvent", () => {
  it("returns true for heartbeat", () => {
    expect(isHeartbeatEvent({ type: "heartbeat" })).toBe(true);
  });

  it("returns false for non-heartbeat", () => {
    expect(isHeartbeatEvent({ type: "final" })).toBe(false);
  });
});

describe("assertEventTypeExhaustive", () => {
  it("does not throw for known event types", () => {
    expect(() => assertEventTypeExhaustive({ type: "message", role: "agent", agent_name: "", content: "" })).not.toThrow();
    expect(() => assertEventTypeExhaustive({ type: "heartbeat" })).not.toThrow();
    expect(() => assertEventTypeExhaustive({ type: "final" })).not.toThrow();
    expect(() => assertEventTypeExhaustive({ type: "error", message: "" })).not.toThrow();
    expect(() => assertEventTypeExhaustive({ type: "score", agent_name: "", criterion: "", value: 0 })).not.toThrow();
  });
});
