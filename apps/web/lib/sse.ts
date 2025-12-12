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

const DEFAULT_RETRY = [1000, 2000, 5000, 10000];

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
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptsRef = useRef(0);
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

      const source = new EventSource(url, { withCredentials });
      eventSourceRef.current = source;

      source.onopen = () => {
        if (cancelled) {
          source.close();
          return;
        }
        attemptsRef.current = 0;
        setStatus("connected");
        setLastError(null);
      };

      source.onmessage = (event) => {
        if (cancelled) return;
        try {
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
  };
}
