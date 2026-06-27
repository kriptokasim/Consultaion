'use client'

import { useCallback, useEffect, useRef, useState } from "react";

export type SSEStatus = "idle" | "connecting" | "connected" | "reconnecting" | "closed";

export type UseEventSourceOptions<T> = {
  enabled?: boolean;
  withCredentials?: boolean;
  parseJson?: boolean;
  retryDelays?: number[];
  onEvent?: (data: T, event: MessageEvent) => void;
  onError?: (event: Event) => void;
};

const DEFAULT_RETRY = [2000, 4000, 8000, 15000];

export function useEventSource<T = unknown>(
  url: string | null,
  options: UseEventSourceOptions<T> = {},
) {
  const {
    enabled = true,
    withCredentials = false,
    parseJson = true,
    retryDelays = DEFAULT_RETRY,
    onEvent,
    onError,
  } = options;
  const [status, setStatus] = useState<SSEStatus>(!url || !enabled ? "idle" : "connecting");
  const [lastEvent, setLastEvent] = useState<T | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptsRef = useRef(0);
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

      source.onopen = () => {
        if (cancelled) {
          source.close();
          return;
        }
        attemptsRef.current = 0;
        setRetryCount(0);
        setStatus("connected");
        setLastError(null);
      };

      source.onmessage = (event) => {
        if (cancelled) return;
        try {
          if (event.lastEventId) {
            lastEventIdRef.current = event.lastEventId;
          }
          const payload = parseJson ? (JSON.parse(event.data) as T) : ((event.data as unknown) as T);
          setLastEvent(payload);
          onEventRef.current?.(payload, event);
        } catch (error) {
          setLastError(error instanceof Error ? error.message : "Failed to parse event");
        }
      };

      source.onerror = (errorEvent) => {
        if (cancelled) return;
        setLastError("stream_error");
        onErrorRef.current?.(errorEvent);

        // Close current source before scheduling retry
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
  }, [url, enabled, parseJson, retryDelays, withCredentials, close, clearRetryTimer]);

  return {
    status,
    lastEvent,
    error: lastError,
    close,
    retryCount,
  };
}

export type SessionStreamEvent = {
  id: string;
  sequence: number;
  event: string;
  session_id: string;
  timestamp: string;
  payload: any;
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
        attemptsRef.current = 0;
        setRetryCount(0);
        setStatus("connected");
        setLastError(null);
      };

      source.onmessage = (event) => {
        if (cancelled) return;
        try {
          const envelope = JSON.parse(event.data) as SessionStreamEvent;
          const seq = envelope.sequence;

          // Deduplication / gap verification
          if (seq !== undefined && lastReceivedSequenceRef.current !== null && seq <= lastReceivedSequenceRef.current) {
            console.log(`[SSE] Discarding duplicate event sequence: ${seq}`);
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
