import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { BrowserDeltaBatcher } from "./browserDeltaBatcher"
import type { ModelResponseDeltaPayload } from "@/lib/streaming/types"

function makeDelta(
  text: string,
  seq: number,
  responseId = "resp-1",
): ModelResponseDeltaPayload {
  return {
    response_id: responseId,
    text,
    delta_sequence: seq,
    accumulated_chars: text.length,
    run_attempt: 1,
    retry_generation: 0,
  } as ModelResponseDeltaPayload
}

describe("BrowserDeltaBatcher", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("flushes immediately on first delta", () => {
    const handler = vi.fn()
    const batcher = new BrowserDeltaBatcher(handler)
    batcher.add(makeDelta("Hello", 1))
    // rAF not yet fired — pending
    expect(handler).not.toHaveBeenCalled()
  })

  it("batches subsequent deltas for the same response", () => {
    const handler = vi.fn()
    const batcher = new BrowserDeltaBatcher(handler)
    batcher.add(makeDelta("Hello", 1))
    batcher.add(makeDelta(" world", 2))
    expect(handler).not.toHaveBeenCalled()
    batcher.flush()
    expect(handler).toHaveBeenCalledTimes(1)
    const envelopes = handler.mock.calls[0][0]
    expect(envelopes).toHaveLength(1)
    expect(envelopes[0].text).toBe(" world")
    expect(envelopes[0].sequence).toBe(2)
  })

  it("keeps different response IDs separate", () => {
    const handler = vi.fn()
    const batcher = new BrowserDeltaBatcher(handler)
    batcher.add(makeDelta("A", 1, "resp-1"))
    batcher.add(makeDelta("B", 1, "resp-2"))
    batcher.flush()
    expect(handler).toHaveBeenCalledTimes(1)
    const envelopes = handler.mock.calls[0][0]
    expect(envelopes).toHaveLength(2)
    expect(envelopes[0].responseId).toBe("resp-1")
    expect(envelopes[1].responseId).toBe("resp-2")
  })

  it("flush sends all pending then clears", () => {
    const handler = vi.fn()
    const batcher = new BrowserDeltaBatcher(handler)
    batcher.add(makeDelta("A", 1))
    batcher.add(makeDelta("B", 2))
    batcher.flush()
    expect(handler).toHaveBeenCalledTimes(1)
    expect(handler.mock.calls[0][0]).toHaveLength(1)
    batcher.flush()
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it("cancel clears pending and stops future adds", () => {
    const handler = vi.fn()
    const batcher = new BrowserDeltaBatcher(handler)
    batcher.add(makeDelta("A", 1))
    batcher.cancel()
    batcher.add(makeDelta("B", 2))
    batcher.flush()
    expect(handler).not.toHaveBeenCalled()
  })

  it("rAF triggers flush", () => {
    const handler = vi.fn()
    const batcher = new BrowserDeltaBatcher(handler)
    batcher.add(makeDelta("A", 1))
    expect(handler).not.toHaveBeenCalled()
    vi.advanceTimersToNextFrame()
    expect(handler).toHaveBeenCalledTimes(1)
    batcher.cancel()
  })

  it("preserves highest sequence on merge", () => {
    const handler = vi.fn()
    const batcher = new BrowserDeltaBatcher(handler)
    batcher.add(makeDelta("low", 1))
    batcher.add(makeDelta("high", 5))
    batcher.flush()
    expect(handler.mock.calls[0][0][0].sequence).toBe(5)
  })
})
