"use client";

import { useEffect, useMemo, useRef, useState, useCallback, Suspense } from "react";
import { useParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { Loader2, AlertCircle, ExternalLink } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SkeletonCard } from "@/components/arena/ModelCard";
import { useRunWorkspace } from "@/hooks/useRunWorkspace";
import { useToast } from "@/components/ui/toast";
import { TimelineEvent } from "@/lib/timeline/types";
import { fetchWithAuth } from "@/lib/auth";
import { API_ORIGIN } from "@/lib/config/runtime";
import { normalizeEvent } from "@/lib/api/normalizeEvent";
import { PipelineProgress, derivePipelineStage } from "@/components/arena/PipelineProgress";
import type { DebateEvent, ScoreItem, Member, JudgeVoteFlow, VotePayload } from "@/lib/api/types";
import { WorkspaceHeader, DesktopStageRail, MobileStageBar, PerspectivesGrid, PerspectivesReadyAction } from "@/components/workspace";
import { FeatureGate, useFeatureFlag } from "@/components/FeatureGate";
import { deriveWorkspaceStage } from "@/lib/workspace/deriveWorkspaceStage";
import type { WorkspaceModelSlot } from "@/lib/workspace/types";
import { AVAILABLE_MODELS } from "@/components/arena/ModelPanelSheet";

// Lazy-load heavy view components
const DebateArena = dynamic(() => import("@/components/debate/DebateArena"), { loading: () => <div className="animate-pulse h-64 bg-muted rounded-xl" /> });
const ParliamentRunView = dynamic(() => import("@/components/parliament/ParliamentRunView"), { loading: () => <div className="animate-pulse h-64 bg-muted rounded-xl" /> });
const CompareRunView = dynamic(() => import("@/components/compare/CompareRunView"), { loading: () => <div className="animate-pulse h-64 bg-muted rounded-xl" /> });
const ConversationRunView = dynamic(() => import("@/components/conversation/ConversationRunView"), { loading: () => <div className="animate-pulse h-64 bg-muted rounded-xl" /> });
const ArenaRunView = dynamic(() => import("@/components/arena/ArenaRunView"), { loading: () => <div className="animate-pulse h-64 bg-muted rounded-xl" /> });
const VotingRunView = dynamic(() => import("@/components/voting/VotingRunView"), { loading: () => <div className="animate-pulse h-64 bg-muted rounded-xl" /> });

/** Statuses that indicate a debate has finished and results should be shown */
const COMPLETED_STATUSES = new Set(["completed", "success", "completed_budget"]);
const TERMINAL_STATUSES = new Set(["completed", "success", "completed_budget", "failed"]);

/** Polling interval for non-completed debates (fallback for SSE) */
const POLL_INTERVAL_MS = 4000;

export default function RunDetailClient({ runId }: { runId?: string } = {}) {
  const params = useParams();
  const router = useRouter();
  const id = runId || (params?.id as string);
  const [showMobileDetails, setShowMobileDetails] = useState(false);
  const {
    debate,
    events,
    status: workspaceStatus,
    sseStatus,
    error: workspaceError,
    outcomeUnknown,
    isPollingFallback,
    continueRun,
    retryRun,
    refetch,
    isContinuing,
  } = useRunWorkspace(id);

  // --- Results data for completed debates (ParliamentRunView) ---
  const [resultsEvents, setResultsEvents] = useState<DebateEvent[]>([]);
  const [resultsMembers, setResultsMembers] = useState<Member[]>([]);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsFetched, setResultsFetched] = useState(false);

  const isCompleted = !!debate && COMPLETED_STATUSES.has(debate.status);
  const isLoading = workspaceStatus === "loading" || (!debate && workspaceStatus !== "failed" && workspaceStatus !== "error");
  const debateError = workspaceError ? new Error(workspaceError) : null;

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

  const { pushToast } = useToast();

  const handleContinue = useCallback(async () => {
    if (!id || isContinuing) return;
    try {
      await continueRun();
    } catch (err) {
      console.error("Failed to continue:", err);
      pushToast({
        title: "Pipeline Error",
        description: "Error resuming the decision pipeline. Please try again.",
        variant: "error",
      });
    }
  }, [id, isContinuing, continueRun, pushToast]);

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

  // Elapsed time tracking
  useEffect(() => {
    if (isCompleted || debate?.status === "failed") return;

    if (!startTimeRef.current && debate?.created_at) {
      const parsedStart = new Date(debate.created_at).getTime();
      if (!isNaN(parsedStart)) {
        startTimeRef.current = parsedStart;
      }
    }

    const interval = setInterval(() => {
      if (startTimeRef.current) {
        setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isCompleted, debate?.status, debate?.created_at]);

  const liveResponseCount = useMemo(() => {
    return events.filter((e: any) => {
      const eventType = e.type || e.payload?.type;
      const payload = e.payload || e;

      return (
        ["arena_response", "message", "seat_message", "model_response"].includes(eventType) ||
        typeof payload.text === "string" ||
        typeof payload.content === "string"
      );
    }).length;
  }, [events]);

  const responsesReceived = useMemo(() => {
    if (typeof debate?.responses_received === "number" && debate.responses_received > 0) {
      return debate.responses_received;
    }
    return liveResponseCount;
  }, [debate?.responses_received, liveResponseCount]);

  const pipelineStage = useMemo(() => {
    if (!debate) return "queued";
    return debate.current_stage || "queued";
  }, [debate]);

  const modelsExpected = useMemo(() => {
    return debate?.models_expected || debate?.final_meta?.models?.length || (debate?.config as any)?.models?.length || 4;
  }, [debate]);

  const scoresReceived = useMemo(() => {
    if (typeof debate?.scores_received === "number") {
      return debate.scores_received;
    }
    return events.filter((e) => e.type === "score").length;
  }, [debate?.scores_received, events]);

  const eventTypes = useMemo(() => new Set(events.map((e: any) => e.type)), [events]);

  const currentWorkspaceStage = useMemo(() => {
    return deriveWorkspaceStage(debate, eventTypes, liveResponseCount);
  }, [debate, eventTypes, liveResponseCount]);

  const modelSlots = useMemo<WorkspaceModelSlot[]>(() => {
    const modelsList = debate?.final_meta?.models || (debate?.config as any)?.models || [];
    return modelsList.map((model: any) => {
      const modelId = typeof model === "string" ? model : model.model_id;
      const matchingDetail = AVAILABLE_MODELS.find((m) => m.id === modelId);
      const displayName = typeof model === "object" ? model.display_name : (matchingDetail?.name || modelId);
      const provider = typeof model === "object" ? model.provider : (matchingDetail?.providerKey || "AI");
      const logoUrl = typeof model === "object" ? model.logo_url : undefined;

      const respEvent = events.find((e: any) => {
        const payload = e.payload || e;
        return e.type === "arena_response" && (payload.model_id === modelId || payload.display_name === displayName);
      });

      const payload = (respEvent?.payload || respEvent) as any;
      const state = respEvent
        ? (payload.success === false ? "failed" : "complete")
        : (currentWorkspaceStage === "collecting_perspectives" ? "streaming" : "queued");

      return {
        model_id: modelId,
        display_name: displayName,
        provider: provider,
        logo_url: logoUrl,
        state: state as any,
        content: payload?.content || payload?.text || undefined,
      };
    });
  }, [debate, events, currentWorkspaceStage]);

  if (isLoading) {
    return (
      <div className="container max-w-[1400px] py-6 space-y-6">
        {/* Header Skeleton */}
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="h-6 w-32 bg-slate-200 dark:bg-slate-800 rounded-md" />
            <div className="h-4 w-64 bg-slate-100 dark:bg-slate-900 rounded-md" />
          </div>
          <div className="h-9 w-24 bg-slate-200 dark:bg-slate-800 rounded-md" />
        </div>

        {/* Question Banner Skeleton */}
        <div className="rounded-2xl border border-slate-200/60 dark:border-slate-800/80 bg-card p-6 space-y-3">
          <div className="flex items-start gap-3">
            <div className="h-10 w-10 rounded-xl bg-slate-200 dark:bg-slate-800 shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-3.5 w-24 bg-slate-200 dark:bg-slate-800 rounded-md" />
              <div className="h-5 w-full bg-slate-100 dark:bg-slate-900 rounded-md" />
              <div className="h-5 w-3/4 bg-slate-100 dark:bg-slate-900 rounded-md" />
            </div>
          </div>
        </div>

        {/* Pipeline Progress Skeleton */}
        <div className="h-14 w-full bg-slate-105 dark:bg-slate-900/60 rounded-2xl animate-pulse" />

        {/* Model Cards Grid Skeleton */}
        <div className="space-y-3 animate-pulse">
          <div className="h-4.5 w-36 bg-slate-200 dark:bg-slate-800 rounded-md" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <SkeletonCard index={0} />
            <SkeletonCard index={1} />
            <SkeletonCard index={2} />
            <SkeletonCard index={3} />
          </div>
        </div>
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
          <ArenaRunView debate={debate} events={resultsEvents} profile={profile} onRefetch={refetch} />
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
      <div className="container max-w-[1400px] py-6 space-y-6">
        {/* Header Skeleton */}
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="h-6 w-32 bg-slate-200 dark:bg-slate-800 rounded-md" />
            <div className="h-4 w-64 bg-slate-100 dark:bg-slate-900 rounded-md" />
          </div>
          <div className="h-9 w-24 bg-slate-200 dark:bg-slate-800 rounded-md" />
        </div>

        {/* Question Banner Skeleton */}
        <div className="rounded-2xl border border-slate-200/60 dark:border-slate-800/80 bg-card p-6 space-y-3">
          <div className="flex items-start gap-3">
            <div className="h-10 w-10 rounded-xl bg-slate-200 dark:bg-slate-800 shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-3.5 w-24 bg-slate-200 dark:bg-slate-800 rounded-md" />
              <div className="h-5 w-full bg-slate-100 dark:bg-slate-900 rounded-md" />
              <div className="h-5 w-3/4 bg-slate-100 dark:bg-slate-900 rounded-md" />
            </div>
          </div>
        </div>

        {/* Pipeline Progress Skeleton */}
        <div className="h-14 w-full bg-slate-105 dark:bg-slate-900/60 rounded-2xl animate-pulse" />

        {/* Model Cards Grid Skeleton */}
        <div className="space-y-3 animate-pulse">
          <div className="h-4.5 w-36 bg-slate-200 dark:bg-slate-800 rounded-md" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <SkeletonCard index={0} />
            <SkeletonCard index={1} />
            <SkeletonCard index={2} />
            <SkeletonCard index={3} />
          </div>
        </div>
      </div>
    );
  }

  // Running / queued debates → live stream view with pipeline progress
  const liveEvents = events.map((e: any) => e.payload || e);

  // Show pipeline progress for arena mode running debates
  if (debate?.mode === "arena" && !isCompleted) {
    return (
      <FeatureGate flag="unifiedWorkspace" fallback={
        <div className="flex flex-col h-[calc(100vh-4rem)]">
          {isPollingFallback && (
            <div className="flex items-center gap-2 px-4 py-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800">
              <Loader2 className="h-3 w-3 animate-spin" />
              <span>Connection interrupted — using polling fallback</span>
            </div>
          )}
          <DebateArena debate={debate} events={events} connectionStatus={sseStatus} />
        </div>
      }>
        <div className="container max-w-[1400px] py-6 space-y-6">
          <WorkspaceHeader
            stage={currentWorkspaceStage}
            prompt={debate?.prompt}
            mode="arena"
            modelCount={modelsExpected}
            onBack={() => router.push("/live")}
          />

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Sidebar for Progress on Desktop */}
            <div className="hidden lg:block lg:col-span-1">
              <DesktopStageRail
                currentStage={currentWorkspaceStage}
                elapsedSeconds={elapsedSeconds}
              />
            </div>

            {/* Main workspace area */}
            <div className="col-span-1 lg:col-span-3 space-y-6">
              {/* Mobile progress bar */}
              <div className="block lg:hidden">
                <FeatureGate flag="mobileWorkspaceV2" fallback={
                  <div className="text-xs text-muted-foreground px-2 py-1 text-center border-b">
                    Running...
                  </div>
                }>
                  <MobileStageBar
                    currentStage={currentWorkspaceStage}
                    responsesReceived={responsesReceived}
                    modelsExpected={modelsExpected}
                    elapsedSeconds={elapsedSeconds}
                    showDetails={showMobileDetails}
                    onToggleDetails={() => setShowMobileDetails(!showMobileDetails)}
                  />
                </FeatureGate>
              </div>

              {/* Perspectives Action when ready */}
              <FeatureGate flag="stagedDecisionPipelinePublic">
                {currentWorkspaceStage === "perspectives_ready" && (
                  <PerspectivesReadyAction
                    mode="arena"
                    modelCount={modelsExpected}
                    onContinue={handleContinue}
                    isContinuing={isContinuing}
                    outcomeUnknown={outcomeUnknown}
                  />
                )}
              </FeatureGate>

              {/* Perspectives Grid during collecting/streaming */}
              {["contacting_models", "collecting_perspectives", "perspectives_ready"].includes(currentWorkspaceStage) ? (
                <PerspectivesGrid modelSlots={modelSlots} />
              ) : (
                /* Once past perspectives generation, show the standard synthesis/arena view */
                <ArenaRunView debate={debate as any} events={liveEvents as any} onRefetch={refetch} />
              )}

              {isPollingFallback && (
                <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>Connection interrupted — using polling fallback</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </FeatureGate>
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
      {isPollingFallback && (
        <div className="flex items-center gap-2 px-4 py-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Connection interrupted — using polling fallback</span>
        </div>
      )}
      {debate?.status === "perspectives_ready" && (
        <div className="px-6 py-4 bg-amber-50/60 border-b border-amber-200 dark:bg-stone-900/40 dark:border-stone-850">
          <div className="max-w-4xl mx-auto flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-stone-900 dark:text-stone-100 flex items-center gap-2">
                <span className="flex h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                Perspectives Collected
              </h3>
              <p className="text-xs text-stone-600 dark:text-stone-400">
                {outcomeUnknown
                  ? "Request was sent but the outcome is unknown. You can safely retry — idempotency will prevent duplicate work."
                  : "All individual agent responses are in. Click below to continue and generate the decision-ready report."}
              </p>
            </div>
            <Button
              onClick={handleContinue}
              disabled={isContinuing}
              size="sm"
              className="bg-amber-600 hover:bg-amber-700 text-white dark:bg-amber-500 dark:hover:bg-amber-600 font-semibold rounded-lg shrink-0"
            >
              {outcomeUnknown ? (
                "Retry Synthesis"
              ) : isContinuing ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                  Synthesizing...
                </>
              ) : (
                "Synthesize Verdict"
              )}
            </Button>
          </div>
        </div>
      )}
      <DebateArena
        debate={debate}
        events={events}
        connectionStatus={sseStatus}
      />
    </div>
  );
}
