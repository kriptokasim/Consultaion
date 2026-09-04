'use client'

import { useCallback, useEffect, useRef, useState } from "react";

export type SSEStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "closed"
  | "unavailable";

export type UseEventSourceOptions<T> = {
  enabled?: boolean;
  withCredentials?: boolean;
  parseJson?: boolean;
  retryDelays?: number[];
  /** Reconnect attempts before the stream is declared unavailable. */
  maxRetries?: number;
  onEvent?: (data: T, event: MessageEvent) => void;
  onError?: (event: Event) => void;
};

const DEFAULT_RETRY = [2000, 4000, 8000, 15000];
const DEFAULT_MAX_RETRIES = 6;
const MAX_RETRY_AFTER_MS = 300000;

/**
 * The backend refuses excess concurrent streams with a named `stream_unavailable`
 * event carrying `retry_after` seconds. Named events never reach `onmessage`, so
 * it needs its own listener; the payload is the only backpressure signal an
 * EventSource can observe (a 503 surfaces as a bare `onerror`).
 */
function parseRetryAfterMs(raw: unknown): number | null {
  if (typeof raw !== "string") return null;
  try {
    const parsed = JSON.parse(raw) as { retry_after?: unknown };
    const seconds =
      typeof parsed.retry_after === "number"
        ? parsed.retry_after
        : typeof parsed.retry_after === "string"
          ? Number(parsed.retry_after)
          : NaN;
    if (!Number.isFinite(seconds) || seconds <= 0) return null;
    return Math.min(seconds * 1000, MAX_RETRY_AFTER_MS);
  } catch {
    return null;
  }
}

export function useEventSource<T = unknown>(
  url: string | null,
  options: UseEventSourceOptions<T> = {},
) {
  const {
    enabled = true,
    withCredentials = false,
    parseJson = true,
    retryDelays = DEFAULT_RETRY,
    maxRetries = DEFAULT_MAX_RETRIES,
    onEvent,
    onError,
  } = options;
  const [status, setStatus] = useState<SSEStatus>(!url || !enabled ? "idle" : "connecting");
  const [lastError, setLastError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [retryAfterMs, setRetryAfterMs] = useState<number | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptsRef = useRef(0);
  const retryAfterMsRef = useRef<number | null>(null);
  const lastEventIdRef = useRef<string | null>(null);
  const onEventRef = useRef(onEvent);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const clearRetryTimer = useCallback(() => {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  }, []);

  const close = useCallback(() => {
    clearRetryTimer();
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setStatus("closed");
  }, [clearRetryTimer]);

  useEffect(() => {
    lastEventIdRef.current = null;
    setRetryCount(0);
    setRetryAfterMs(null);
    attemptsRef.current = 0;
    retryAfterMsRef.current = null;
  }, [url]);

  useEffect(() => {
    if (!url || !enabled) {
      close();
      setStatus("idle");
      return () => undefined;
    }

    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      const attempt = attemptsRef.current;
      setStatus(attempt > 0 ? "reconnecting" : "connecting");

      let finalUrl = url;
      if (lastEventIdRef.current !== null) {
        try {
          const urlObj = new URL(url, window.location.origin);
          urlObj.searchParams.set("last_sequence", lastEventIdRef.current);
          finalUrl = urlObj.toString();
        } catch {
          const separator = url.includes("?") ? "&" : "?";
          finalUrl = `${url}${separator}last_sequence=${lastEventIdRef.current}`;
        }
      }

      const source = new EventSource(finalUrl, { withCredentials });
      eventSourceRef.current = source;

      // Both `onerror` and `stream_unavailable` can fire for the same
      // connection; only the first may schedule a retry.
      let retryScheduled = false;
      const scheduleRetry = (explicitDelay?: number) => {
        if (cancelled || retryScheduled) return;
        retryScheduled = true;

        source.close();
        if (eventSourceRef.current === source) {
          eventSourceRef.current = null;
        }

        attemptsRef.current += 1;
        setRetryCount(attemptsRef.current);

        if (attemptsRef.current > maxRetries) {
          clearRetryTimer();
          setStatus("unavailable");
          return;
        }

        const delay =
          explicitDelay ??
          retryDelays[Math.min(attemptsRef.current - 1, retryDelays.length - 1)];

        clearRetryTimer();
        retryTimerRef.current = setTimeout(() => {
          connect();
        }, delay);
      };

      source.onopen = () => {
        if (cancelled) {
          source.close();
          return;
        }
        performance.mark?.("sse_open");
        attemptsRef.current = 0;
        retryAfterMsRef.current = null;
        setRetryCount(0);
        setRetryAfterMs(null);
        setStatus("connected");
        setLastError(null);
      };

      source.addEventListener("stream_unavailable", (event) => {
        if (cancelled) return;
        const delay = parseRetryAfterMs((event as MessageEvent).data);
        retryAfterMsRef.current = delay;
        setRetryAfterMs(delay);
        setLastError("stream_unavailable");
        scheduleRetry(delay ?? undefined);
      });

      let _firstEvent = true;
      source.onmessage = (event) => {
        if (cancelled) return;
        if (_firstEvent) {
          _firstEvent = false;
          performance.mark?.("sse_first_event");
        }
        try {
          if (event.lastEventId) {
            lastEventIdRef.current = event.lastEventId;
          }
          const payload = parseJson ? (JSON.parse(event.data) as T) : ((event.data as unknown) as T);
          onEventRef.current?.(payload, event);
        } catch (error) {
          setLastError(error instanceof Error ? error.message : "Failed to parse event");
        }
      };

      source.onerror = (errorEvent) => {
        if (cancelled) return;
        if (!retryScheduled) {
          setLastError("stream_error");
        }
        onErrorRef.current?.(errorEvent);

        // A 503 refusal carries `Retry-After` the EventSource cannot read, so
        // fall back to the ladder and let the attempt cap end the storm.
        scheduleRetry(retryAfterMsRef.current ?? undefined);
      };
    };

    connect();

    return () => {
      cancelled = true;
      close();
    };
  }, [
    url,
    enabled,
    parseJson,
    retryDelays,
    maxRetries,
    withCredentials,
    close,
    clearRetryTimer,
  ]);

  return {
    status,
    error: lastError,
    close,
    retryCount,
    retryAfterMs,
  };
}

export type SessionStreamEvent = {
  id: string;
  sequence: number;
  event: string;
  session_id: string;
  timestamp: string;
  payload: Record<string, unknown>;
};

export type UseSessionStreamOptions = {
  enabled?: boolean;
  withCredentials?: boolean;
  retryDelays?: number[];
  onEvent?: (event: SessionStreamEvent) => void;
  onError?: (event: Event) => void;
};

export function useSessionStream(
  url: string | null,
  options: UseSessionStreamOptions = {},
) {
  const {
    enabled = true,
    withCredentials = false,
    retryDelays = DEFAULT_RETRY,
    onEvent,
    onError,
  } = options;

  const [status, setStatus] = useState<SSEStatus>(!url || !enabled ? "idle" : "connecting");
  const [events, setEvents] = useState<SessionStreamEvent[]>([]);
  const [lastError, setLastError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptsRef = useRef(0);
  const lastReceivedSequenceRef = useRef<number | null>(null);
  
  const onEventRef = useRef(onEvent);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const clearRetryTimer = useCallback(() => {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  }, []);

  const close = useCallback(() => {
    clearRetryTimer();
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setStatus("closed");
  }, [clearRetryTimer]);

  // Reset sequence/events when URL changes
  useEffect(() => {
    lastReceivedSequenceRef.current = null;
    setEvents([]);
    setRetryCount(0);
    attemptsRef.current = 0;
  }, [url]);

  useEffect(() => {
    if (!url || !enabled) {
      close();
      setStatus("idle");
      return () => undefined;
    }

    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      const attempt = attemptsRef.current;
      setStatus(attempt > 0 ? "reconnecting" : "connecting");

      // Format URL to include last_sequence parameter
      let finalUrl = url;
      if (lastReceivedSequenceRef.current !== null) {
        try {
          const urlObj = new URL(url);
          urlObj.searchParams.set("last_sequence", lastReceivedSequenceRef.current.toString());
          finalUrl = urlObj.toString();
        } catch {
          const separator = url.includes("?") ? "&" : "?";
          finalUrl = `${url}${separator}last_sequence=${lastReceivedSequenceRef.current}`;
        }
      }

      const source = new EventSource(finalUrl, { withCredentials });
      eventSourceRef.current = source;

      source.onopen = () => {
        if (cancelled) {
          source.close();
          return;
        }
        performance.mark?.("sse_open");
        attemptsRef.current = 0;
        setRetryCount(0);
        setStatus("connected");
        setLastError(null);
      };

      let _sessionFirstEvent = true;
      source.onmessage = (event) => {
        if (cancelled) return;
        if (_sessionFirstEvent) {
          _sessionFirstEvent = false;
          performance.mark?.("sse_first_event");
        }
        try {
          const envelope = JSON.parse(event.data) as SessionStreamEvent;
          const seq = envelope.sequence;

          // Deduplication / gap verification
          if (seq !== undefined && lastReceivedSequenceRef.current !== null && seq <= lastReceivedSequenceRef.current) {
            // F2: Guard console spam in production (Patchset 148)
            if (process.env.NODE_ENV !== "production") {
              console.log(`[SSE] Discarding duplicate event sequence: ${seq}`);
            }
            return;
          }

          if (seq !== undefined) {
            lastReceivedSequenceRef.current = seq;
          }

          setEvents((prev) => {
            // Check list for duplicates as secondary guard
            if (seq !== undefined && prev.some((e) => e.sequence === seq)) {
              return prev;
            }
            const next = [...prev, envelope];
            // Cap event list to prevent memory growth in long sessions
            const MAX_STREAM_EVENTS = 500;
            return next.length > MAX_STREAM_EVENTS ? next.slice(next.length - MAX_STREAM_EVENTS) : next;
          });

          onEventRef.current?.(envelope);
        } catch (error) {
          console.error("[SSE] Failed to parse event envelope:", error);
          setLastError(error instanceof Error ? error.message : "Failed to parse event");
        }
      };

      source.onerror = (errorEvent) => {
        if (cancelled) return;
        setLastError("stream_error");
        onErrorRef.current?.(errorEvent);

        source.close();
        if (eventSourceRef.current === source) {
          eventSourceRef.current = null;
        }

        attemptsRef.current += 1;
        setRetryCount(attemptsRef.current);
        const delay = retryDelays[Math.min(attemptsRef.current - 1, retryDelays.length - 1)];

        clearRetryTimer();
        retryTimerRef.current = setTimeout(() => {
          connect();
        }, delay);
      };
    };

    connect();

    return () => {
      cancelled = true;
      close();
    };
  }, [url, enabled, retryDelays, withCredentials, close, clearRetryTimer]);

  return {
    status,
    events,
    error: lastError,
    close,
    retryCount,
  };
}
