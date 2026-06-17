/**
 * Client-side event player for the deterministic demo.
 *
 * FH111: Replays streaming events from a fixture file with compressed timing.
 * No provider dependency, no Celery, no gateway. Explicit "Interactive product demo" label.
 */

"use client";

import { useCallback, useRef, useState } from "react";
import { trackEvent } from "@/lib/analytics";
import type { StreamEnvelope, StreamingModelBuffer } from "@/lib/streaming/types";

export interface DemoPlayerState {
  isPlaying: boolean;
  isPaused: boolean;
  currentIndex: number;
  totalEvents: number;
  buffers: Map<string, StreamingModelBuffer>;
  elapsed: number;
  error: string | null;
}

const TIMING_MULTIPLIER = 0.15; // Compress demo: 15% of real timing

export function useDemoPlayer(fixture: StreamEnvelope[]) {
  const [state, setState] = useState<DemoPlayerState>({
    isPlaying: false,
    isPaused: false,
    currentIndex: 0,
    totalEvents: fixture.length,
    buffers: new Map(),
    elapsed: 0,
    error: null,
  });

  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const startTimeRef = useRef<number>(0);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  }, []);

  const applyEvent = useCallback((event: StreamEnvelope, buffers: Map<string, StreamingModelBuffer>) => {
    const { type, response_id, payload } = event;
    const p = event.payload as Record<string, unknown>;

    switch (type) {
      case "model_response_connecting": {
        if (!response_id) break;
        const next = new Map(buffers);
        next.set(response_id, {
          responseId: response_id,
          modelId: (p.model_id as string) || "",
          displayName: (p.display_name as string) || "",
          provider: (p.provider as string) || "",
          state: "connecting",
          accumulatedText: "",
          lastSequence: 0,
        });
        return next;
      }
      case "model_response_started": {
        if (!response_id) break;
        const buf = buffers.get(response_id);
        if (buf) {
          const next = new Map(buffers);
          next.set(response_id, { ...buf, state: "streaming" });
          return next;
        }
        break;
      }
      case "model_response_delta": {
        if (!response_id) break;
        const buf = buffers.get(response_id);
        if (buf) {
          const next = new Map(buffers);
          next.set(response_id, {
            ...buf,
            accumulatedText: buf.accumulatedText + (p.text as string),
            lastSequence: (p.delta_sequence as number) || buf.lastSequence + 1,
          });
          return next;
        }
        break;
      }
      case "model_response_persisting": {
        if (!response_id) break;
        const buf = buffers.get(response_id);
        if (buf) {
          const next = new Map(buffers);
          next.set(response_id, { ...buf, state: "persisting" });
          return next;
        }
        break;
      }
      case "model_response_completed": {
        if (!response_id) break;
        const next = new Map(buffers);
        next.delete(response_id);
        return next;
      }
      case "model_response_failed": {
        if (!response_id) break;
        const buf = buffers.get(response_id);
        if (buf) {
          const next = new Map(buffers);
          next.set(response_id, { ...buf, state: "failed" });
          return next;
        }
        break;
      }
    }
    return buffers;
  }, []);

  const play = useCallback(() => {
    clearTimers();
    trackEvent("demo_started");
    startTimeRef.current = Date.now();
    let buffers = new Map<string, StreamingModelBuffer>();
    let prevTs = 0;

    const schedule = (index: number) => {
      if (index >= fixture.length) {
        setState(s => ({ ...s, isPlaying: false, isPaused: false, currentIndex: index }));
        trackEvent("demo_report_revealed");
        return;
      }

      const event = fixture[index];
      const eventTs = new Date(event.timestamp).getTime();
      const gap = index === 0 ? 0 : Math.max(0, (eventTs - prevTs) * TIMING_MULTIPLIER);
      prevTs = eventTs;

      const timer = setTimeout(() => {
        buffers = applyEvent(event, buffers);
        // Track first response seen
        if (index === 1) {
          trackEvent("demo_first_response_seen");
        }
        setState(s => ({
          ...s,
          buffers: new Map(buffers),
          currentIndex: index + 1,
          elapsed: Date.now() - startTimeRef.current,
        }));
        schedule(index + 1);
      }, gap);
      timersRef.current.push(timer);
    };

    setState(s => ({
      ...s,
      isPlaying: true,
      isPaused: false,
      currentIndex: 0,
      buffers: new Map(),
      error: null,
    }));
    schedule(0);
  }, [fixture, applyEvent, clearTimers]);

  const pause = useCallback(() => {
    clearTimers();
    setState(s => ({ ...s, isPlaying: false, isPaused: true }));
  }, [clearTimers]);

  const reset = useCallback(() => {
    clearTimers();
    setState(s => ({
      ...s,
      isPlaying: false,
      isPaused: false,
      currentIndex: 0,
      buffers: new Map(),
      elapsed: 0,
    }));
  }, [clearTimers]);

  return { state, play, pause, reset };
}
