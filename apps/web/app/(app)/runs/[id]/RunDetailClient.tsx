"use client";

import { useEffect, useMemo, useReducer, useRef, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { Loader2, AlertCircle, ExternalLink } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import DebateArena from "@/components/debate/DebateArena";
import ParliamentRunView from "@/components/parliament/ParliamentRunView";
import CompareRunView from "@/components/compare/CompareRunView";
import ConversationRunView from "@/components/conversation/ConversationRunView";
import ArenaRunView from "@/components/arena/ArenaRunView";
import VotingRunView from "@/components/voting/VotingRunView";
import { Button } from "@/components/ui/button";
import { useDebate } from "@/lib/api/hooks/useDebate";
import { timelineReducer, initialTimelineState } from "@/lib/timeline/reducer";
import { TimelineEvent } from "@/lib/timeline/types";
import { useEventSource } from "@/lib/sse";
import { fetchWithAuth } from "@/lib/auth";
import { API_ORIGIN } from "@/lib/config/runtime";
import { normalizeEvent } from "@/lib/api/normalizeEvent";
import { PipelineProgress, derivePipelineStage } from "@/components/arena/PipelineProgress";
import type { DebateEvent, ScoreItem, Member, JudgeVoteFlow, VotePayload } from "@/lib/api/types";

/** Statuses that indicate a debate has finished and results should be shown */
const COMPLETED_STATUSES = new Set(["completed", "success", "completed_budget"]);
const TERMINAL_STATUSES = new Set(["completed", "success", "completed_budget", "failed"]);

/** Polling interval for non-completed debates (fallback for SSE) */
const POLL_INTERVAL_MS = 4000;

export default function RunDetailClient() {
  const params = useParams();
  const id = params.id as string;
  const { data: debate, isLoading, error: debateError, refetch } = useDebate(id);
  const [state, dispatch] = useReducer(timelineReducer, initialTimelineState);
  const mounted = useRef(true);

  // --- Results data for completed debates (ParliamentRunView) ---
  const [resultsEvents, setResultsEvents] = useState<DebateEvent[]>([]);
  const [resultsMembers, setResultsMembers] = useState<Member[]>([]);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsFetched, setResultsFetched] = useState(false);

  const isCompleted = !!debate && COMPLETED_STATUSES.has(debate.status);

  // --- Polling state for running debates ---
  const [pollingFallback, setPollingFallback] = useState(false);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  // --- Elapsed time tracking ---
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const startTimeRef = useRef<number | null>(null);

  // Fetch profile to know if user is authenticated for PLG CTAs
  const [profile, setProfile] = useState<any>(null);
  const [profileLoaded, setProfileLoaded] = useState(false);

  useEffect(() => {
    fetchWithAuth('/me')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        setProfile(data);
        setProfileLoaded(true);
        if (!data) {
          import("@/lib/analytics").then(({ trackEvent }) => {
            trackEvent("public_run_viewed", { debate_id: id, is_authenticated: false, referrer: document.referrer });
          });
        }
      })
      .catch(() => {
        setProfile(null);
        setProfileLoaded(true);
      });
  }, [id]);

  // Fetch events + members for completed debates
  useEffect(() => {
    if (!isCompleted || !id || resultsFetched) return;
    setResultsLoading(true);

    Promise.all([
      fetchWithAuth(`/debates/${id}/events`).then((r) => (r.ok ? r.json() : { items: [] })),
      fetchWithAuth(`/debates/${id}/members`).then((r) => (r.ok ? r.json() : { members: [] })),
    ])
      .then(([eventsData, membersData]) => {
        setResultsEvents((eventsData.items || []).map(normalizeEvent));
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

  // --- Initialize start time from debate.created_at ---
  useEffect(() => {
    if (debate?.created_at && !startTimeRef.current) {
      const parsedStart = new Date(debate.created_at).getTime();
      if (!isNaN(parsedStart)) {
        startTimeRef.current = parsedStart;
        setElapsedSeconds(Math.floor((Date.now() - parsedStart) / 1000));
      }
    }
  }, [debate?.created_at]);

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

  // 2. Polling fallback for running debates
  const pollDebate = useCallback(async () => {
    if (!id || isCompleted || !mounted.current) return;
    try {
      await refetch();
    } catch {
      // Silently ignore poll errors
    }
  }, [id, isCompleted, refetch]);

  useEffect(() => {
    if (!id || isCompleted || (debate?.status && TERMINAL_STATUSES.has(debate.status))) {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      return;
    }

    pollTimerRef.current = setInterval(pollDebate, POLL_INTERVAL_MS);
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [id, isCompleted, debate?.status, pollDebate]);

  // 3. Elapsed time tracking
  useEffect(() => {
    if (isCompleted || debate?.status === "failed") return;

    if (!startTimeRef.current) {
      startTimeRef.current = Date.now();
    }

    const interval = setInterval(() => {
      if (startTimeRef.current) {
        setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isCompleted, debate?.status]);

  // 4. Live Updates (SSE) — only for non-completed debates
  const streamUrl =
    id && !isCompleted
      ? `${API_ORIGIN}/debates/${id}/stream`
      : null;
  const { lastEvent, status: sseStatus } = useEventSource<any>(streamUrl, {
    enabled: !!id && !isCompleted,
    withCredentials: true,
    parseJson: true,
  });

  // Track SSE disconnect for fallback indicator
  useEffect(() => {
    if (sseStatus === "reconnecting" || sseStatus === "closed") {
      setPollingFallback(true);
    } else if (sseStatus === "connected") {
      setPollingFallback(false);
    }
  }, [sseStatus]);

  useEffect(() => {
    if (!lastEvent) return;

    try {
      const normalized = normalizeEvent(lastEvent);
      const event: TimelineEvent = {
        id: lastEvent.id || `sse-${Date.now()}-${Math.random()}`,
        debate_id: id,
        ts: lastEvent.ts || new Date().toISOString(),
        type: lastEvent.type,
        round: lastEvent.round || 0,
        seat: lastEvent.seat,
        payload: normalized as unknown as Record<string, unknown>,
      };
      dispatch({ type: "APPEND", event });
    } catch (err) {
      console.error("Error processing SSE event", err);
    }
  }, [lastEvent, id]);

  // Derive pipeline stage for running debates
  const liveResponseCount = useMemo(() => {
    return state.events.filter((e) => e.type === "arena_response").length;
  }, [state.events]);

  const pipelineStage = useMemo(() => {
    if (!debate) return "queued";
    const eventTypes = new Set(state.events.map((e) => e.type));
    return derivePipelineStage(debate, eventTypes, liveResponseCount);
  }, [debate, state.events, liveResponseCount]);

  const modelsExpected = useMemo(() => {
    return debate?.final_meta?.models?.length || (debate?.config as any)?.models?.length || 4;
  }, [debate]);

  const responsesReceived = useMemo(() => {
    const messages = (debate as any)?.messages || [];
    const responseMessages = messages.filter((m: any) => m.role === "arena_response" || m.role === "candidate" || m.role === "message");
    if (responseMessages.length > 0) return responseMessages.length;
    return liveResponseCount;
  }, [debate, liveResponseCount]);

  const scoresReceived = useMemo(() => {
    if (debate?.final_meta?.scores) {
      return Object.keys(debate.final_meta.scores).length;
    }
    return state.events.filter((e) => e.type === "score").length;
  }, [debate, state.events]);

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

  // Handle explicitly failed debates
  if (debate?.status === "failed") {
    const errorReason = debate?.final_meta?.error || debate?.error_reason || "Run encountered a terminal error and failed.";
    return (
      <div className="container py-8 max-w-2xl">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Run Failed</AlertTitle>
          <AlertDescription>
            <p className="mt-2 text-sm">{errorReason}</p>
            <Button variant="outline" className="mt-4" onClick={() => window.location.reload()}>
              Retry / Refresh
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  // Completed debates → rich results view (ParliamentRunView or CompareRunView)
  if (isCompleted && resultsFetched && profileLoaded) {
    if (debate?.mode === "arena") {
      return (
        <div className="container max-w-[1400px] py-6">
          <ArenaRunView debate={debate} events={resultsEvents} profile={profile} />
        </div>
      );
    }
    if (debate?.mode === "compare") {
      return (
        <div className="container max-w-[1400px] h-[calc(100vh-4rem)] py-6">
          <CompareRunView debate={debate} events={resultsEvents} />
        </div>
      );
    }
    if (debate?.mode === "conversation") {
      return (
        <div className="container max-w-5xl h-[calc(100vh-4rem)] py-6">
          <ConversationRunView debate={debate} events={resultsEvents} />
        </div>
      );
    }
    if (debate?.mode === "voting") {
      return (
        <div className="container max-w-6xl py-6">
          <VotingRunView
            debate={debate}
            events={resultsEvents}
            isCompleted={true}
            resultsMembers={resultsMembers}
            judgeVotes={judgeVotes}
            scores={scores}
            vote={vote}
          />
        </div>
      );
    }
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
        <span className="ml-3 text-sm text-muted-foreground">Loading debate results…</span>
      </div>
    );
  }

  // Running / queued debates → live stream view with pipeline progress
  const liveEvents = state.events.map((e: any) => e.payload || e);

  // Show pipeline progress for arena mode running debates
  if (debate?.mode === "arena" && !isCompleted) {
    return (
      <div className="container max-w-[1400px] py-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-stone-900 dark:text-stone-100">Arena Run</h1>
            <p className="text-sm text-stone-500 dark:text-stone-400 truncate max-w-md">{debate?.prompt}</p>
          </div>
          <Button variant="outline" size="sm" asChild>
            <a href="/live">
              New Run
            </a>
          </Button>
        </div>

        <PipelineProgress
          currentStage={pipelineStage}
          elapsedSeconds={elapsedSeconds}
          responsesReceived={responsesReceived}
          modelsExpected={modelsExpected}
          scoresReceived={scoresReceived}
        />

        {pollingFallback && (
          <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>Connection interrupted — using polling fallback</span>
          </div>
        )}

        <ArenaRunView debate={debate as any} events={liveEvents as any} />
      </div>
    );
  }

  if (debate?.mode === "compare" && !isCompleted) {
    return (
      <div className="container max-w-[1400px] h-[calc(100vh-4rem)] py-6">
        <CompareRunView debate={debate as any} events={liveEvents as any} />
      </div>
    );
  }

  if (debate?.mode === "conversation" && !isCompleted) {
    return (
      <div className="container max-w-5xl h-[calc(100vh-4rem)] py-6">
        <ConversationRunView debate={debate as any} events={liveEvents as any} />
      </div>
    );
  }

  if (debate?.mode === "voting" && !isCompleted) {
    return (
      <div className="container max-w-6xl py-6">
        <VotingRunView
          debate={debate as any}
          events={liveEvents as any}
          isCompleted={false}
          connectionStatus={sseStatus}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {pollingFallback && (
        <div className="flex items-center gap-2 px-4 py-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Connection interrupted — using polling fallback</span>
        </div>
      )}
      <DebateArena
        debate={debate}
        events={state.events}
        connectionStatus={sseStatus}
      />
    </div>
  );
}
