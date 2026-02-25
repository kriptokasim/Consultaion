"use client";

import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2, AlertCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import DebateArena from "@/components/debate/DebateArena";
import ParliamentRunView from "@/components/parliament/ParliamentRunView";
import { Button } from "@/components/ui/button";
import { useDebate } from "@/lib/api/hooks/useDebate";
import { timelineReducer, initialTimelineState } from "@/lib/timeline/reducer";
import { TimelineEvent } from "@/lib/timeline/types";
import { useEventSource } from "@/lib/sse";
import { fetchWithAuth } from "@/lib/auth";
import { API_ORIGIN } from "@/lib/config/runtime";
import type { DebateEvent, ScoreItem, Member, JudgeVoteFlow, VotePayload } from "@/lib/api/types";

/** Statuses that indicate a debate has finished and results should be shown */
const COMPLETED_STATUSES = new Set(["completed", "success", "completed_budget"]);

export default function RunDetailClient() {
  const params = useParams();
  const id = params.id as string;
  const { data: debate, isLoading, error: debateError } = useDebate(id);
  const [state, dispatch] = useReducer(timelineReducer, initialTimelineState);
  const mounted = useRef(true);

  // --- Results data for completed debates (ParliamentRunView) ---
  const [resultsEvents, setResultsEvents] = useState<DebateEvent[]>([]);
  const [resultsMembers, setResultsMembers] = useState<Member[]>([]);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsFetched, setResultsFetched] = useState(false);

  const isCompleted = !!debate && COMPLETED_STATUSES.has(debate.status);

  // Fetch events + members for completed debates
  useEffect(() => {
    if (!isCompleted || !id || resultsFetched) return;
    setResultsLoading(true);

    Promise.all([
      fetchWithAuth(`/debates/${id}/events`).then((r) => (r.ok ? r.json() : { items: [] })),
      fetchWithAuth(`/debates/${id}/members`).then((r) => (r.ok ? r.json() : { members: [] })),
    ])
      .then(([eventsData, membersData]) => {
        setResultsEvents(eventsData.items || []);
        setResultsMembers(membersData.members || []);
        setResultsFetched(true);
      })
      .catch((err) => {
        console.error("Failed to fetch results data:", err);
      })
      .finally(() => setResultsLoading(false));
  }, [isCompleted, id, resultsFetched]);

  // Derive scores, judgeVotes, and vote from events
  const { scores, judgeVotes, vote } = useMemo(() => {
    const scoreMap = new Map<string, { total: number; count: number; rationale?: string }>();
    const jv: JudgeVoteFlow[] = [];

    for (const evt of resultsEvents) {
      if (evt.type === "score") {
        const se = evt as DebateEvent & { type: "score"; persona: string; judge: string; score: number; rationale?: string };
        const existing = scoreMap.get(se.persona) || { total: 0, count: 0 };
        existing.total += se.score;
        existing.count += 1;
        existing.rationale = se.rationale;
        scoreMap.set(se.persona, existing);

        jv.push({
          persona: se.persona,
          judge: se.judge,
          score: se.score,
          vote: se.score >= 0.5 ? "aye" : "nay",
          at: (se as any).at,
        });
      }
    }

    const s: ScoreItem[] = Array.from(scoreMap.entries()).map(([persona, data]) => ({
      persona,
      score: data.count > 0 ? data.total / data.count : 0,
      rationale: data.rationale,
    }));

    // Derive vote ranking from sorted scores
    const sorted = s.slice().sort((a, b) => b.score - a.score);
    const v: VotePayload | undefined = sorted.length
      ? { method: "borda", ranking: sorted.map((si) => si.persona) }
      : undefined;

    return { scores: s, judgeVotes: jv, vote: v };
  }, [resultsEvents]);

  // 1. Initial Hydration (REST) — uses authenticated fetch with cookies
  useEffect(() => {
    mounted.current = true;
    if (!id) return;

    async function hydrate() {
      try {
        const res = await fetchWithAuth(`/debates/${id}/timeline`);
        if (!res.ok) throw new Error("Failed to fetch timeline");
        const events: TimelineEvent[] = await res.json();

        if (mounted.current) {
          dispatch({
            type: "INIT",
            events,
            status: debate?.status || "unknown",
            config: (debate?.config as any) || null,
          });
        }
      } catch (err) {
        console.error("Hydration failed:", err);
      }
    }

    if (debate && state.isRecovering) {
      hydrate();
    }

    return () => {
      mounted.current = false;
    };
  }, [id, debate, state.isRecovering]);

  // 2. Live Updates (SSE) — only for non-completed debates
  const authToken = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
  const streamUrl =
    id && !isCompleted
      ? `${API_ORIGIN}/debates/${id}/stream${authToken ? `?token=${authToken}` : ""}`
      : null;
  const { lastEvent, status: sseStatus } = useEventSource<any>(streamUrl, {
    enabled: !!id && !isCompleted,
    withCredentials: true,
    parseJson: true,
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
        payload: lastEvent.payload || lastEvent,
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

  // Completed debates → rich results view (ParliamentRunView)
  if (isCompleted && resultsFetched) {
    return (
      <div className="container max-w-6xl py-6">
        <ParliamentRunView
          id={id}
          debate={debate}
          scores={scores}
          vote={vote}
          events={resultsEvents}
          members={resultsMembers}
          judgeVotes={judgeVotes}
          threshold={0.5}
          voteBasis="threshold"
          apiBase={API_ORIGIN}
        />
      </div>
    );
  }

  // Still loading results for completed debate
  if (isCompleted && resultsLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-3 text-sm text-stone-500">Loading debate results…</span>
      </div>
    );
  }

  // Running / queued debates → live stream view (DebateArena)
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
