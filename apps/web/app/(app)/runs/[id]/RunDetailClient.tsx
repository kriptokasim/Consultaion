"use client";

import { useEffect, useReducer, useRef } from "react";
import { useParams } from "next/navigation";
import { Loader2, AlertCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import DebateArena from "@/components/debate/DebateArena";
import { Button } from "@/components/ui/button";
import { useDebate } from "@/lib/api/hooks/useDebate";
import { timelineReducer, initialTimelineState } from "@/lib/timeline/reducer";
import { TimelineEvent } from "@/lib/timeline/types";
import { useEventSource } from "@/lib/sse";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function RunDetailClient() {
  const params = useParams();
  const id = params.id as string;
  const { data: debate, isLoading, error: debateError } = useDebate(id);
  const [state, dispatch] = useReducer(timelineReducer, initialTimelineState);
  const mounted = useRef(true);

  // 1. Initial Hydration (REST)
  useEffect(() => {
    mounted.current = true;
    if (!id) return;

    async function hydrate() {
      try {
        const res = await fetch(`${API_BASE_URL}/debates/${id}/timeline`);
        if (!res.ok) throw new Error("Failed to fetch timeline");
        const events: TimelineEvent[] = await res.json();

        if (mounted.current) {
          dispatch({
            type: "INIT",
            events,
            status: debate?.status || "unknown",
            config: (debate?.config as any) || null
          });
        }
      } catch (err) {
        console.error("Hydration failed:", err);
      }
    }

    if (debate && state.isRecovering) {
      hydrate();
    }

    return () => { mounted.current = false; };
  }, [id, debate, state.isRecovering]);

  // 2. Live Updates (SSE)
  const streamUrl = id ? `${API_BASE_URL}/debates/${id}/events/stream` : null;
  const { lastEvent, status: sseStatus } = useEventSource<any>(streamUrl, {
    enabled: !!id,
    withCredentials: true,
    parseJson: true
  });

  useEffect(() => {
    if (!lastEvent) return;

    try {
      const event: TimelineEvent = {
        id: lastEvent.id || `sse-${Date.now()}-${Math.random()}`,
        debate_id: id,
        ts: lastEvent.ts || new Date().toISOString(),
        type: lastEvent.type,
        round: lastEvent.round || 0,
        seat: lastEvent.seat,
        payload: lastEvent.payload || lastEvent
      };
      dispatch({ type: "APPEND", event });
    } catch (err) {
      console.error("Error processing SSE event", err);
    }
  }, [lastEvent, id]);

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (debateError) {
    return (
      <div className="container py-8">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error loading debate</AlertTitle>
          <AlertDescription>
            {debateError.message}
            <Button variant="outline" className="mt-4 block" onClick={() => window.location.reload()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <DebateArena
        debate={debate}
        events={state.events}
        connectionStatus={sseStatus}
      />
    </div>
  );
}
