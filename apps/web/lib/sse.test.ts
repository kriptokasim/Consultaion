import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useEventSource } from "./sse";

class MockEventSource {
  static instances: MockEventSource[] = [];

  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn();
  private listeners = new Map<string, Set<(event: Event) => void>>();

  constructor(public url: string, public options?: EventSourceInit) {
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: Event) => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }

  removeEventListener(type: string, listener: (event: Event) => void) {
    this.listeners.get(type)?.delete(listener);
  }

  dispatch(type: string, event: Event) {
    this.listeners.get(type)?.forEach((listener) => listener(event));
  }
}

describe("useEventSource", () => {
  afterEach(() => {
    MockEventSource.instances = [];
    vi.unstubAllGlobals();
  });

  it("delivers messages through the callback without retaining event state", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const onEvent = vi.fn();
    let renderCount = 0;

    const { result } = renderHook(() => {
      renderCount += 1;
      return useEventSource<{ type: string }>("/api/debates/d1/stream", { onEvent });
    });
    const source = MockEventSource.instances[0];

    act(() => source.onopen?.(new Event("open")));
    const rendersAfterOpen = renderCount;

    act(() => {
      source.onmessage?.(new MessageEvent("message", {
        data: JSON.stringify({ type: "heartbeat" }),
        lastEventId: "42",
      }));
    });

    expect(onEvent).toHaveBeenCalledWith(
      { type: "heartbeat" },
      expect.any(MessageEvent),
    );
    expect(renderCount).toBe(rendersAfterOpen);
    expect("lastEvent" in result.current).toBe(false);
  });
});
