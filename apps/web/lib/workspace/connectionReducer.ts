import type { CoreState, ResponsesState, TimelineState, CoreLoadFailure, RunHydrationQuality, RunWorkspaceStatus } from "@/hooks/useRunWorkspace";
import type { SSEStatus } from "@/lib/sse";

export type ConnectionPhase = "idle" | "hydrating" | "streaming" | "polling_fallback" | "terminal" | "error";

export interface ConnectionState {
  phase: ConnectionPhase;
  status: RunWorkspaceStatus; // Derived status for UI
  coreState: CoreState;
  responsesState: ResponsesState;
  timelineState: TimelineState;
  coreErrorCode: CoreLoadFailure | null;
  coreHttpStatus: number | null;
  hydrationQuality: RunHydrationQuality;
  timelineError: string | null;
  eventsError: string | null;
  responsesError: string | null;
  error: string | null;
  isPollingFallback: boolean;
}

export const INITIAL_CONNECTION_STATE: ConnectionState = {
  phase: "idle",
  status: "idle",
  coreState: "idle",
  responsesState: "idle",
  timelineState: "idle",
  coreErrorCode: null,
  coreHttpStatus: null,
  hydrationQuality: "complete",
  timelineError: null,
  eventsError: null,
  responsesError: null,
  error: null,
  isPollingFallback: false,
};

export type ConnectionAction =
  | { type: "HYDRATION_START" }
  | { type: "CORE_LOADED"; isTerminal: boolean; outcome?: "completed" | "failed" }
  | { type: "CORE_FAILED"; code: CoreLoadFailure; httpStatus: number | null; error: string }
  | { type: "RESPONSES_LOADING" }
  | { type: "RESPONSES_LOADED"; count: number }
  | { type: "RESPONSES_FAILED"; isMismatch: boolean; error: string }
  | { type: "TIMELINE_LOADING" }
  | { type: "TIMELINE_LOADED"; quality: RunHydrationQuality; timelineError: string | null; eventsError: string | null }
  | { type: "TIMELINE_FAILED" }
  | { type: "SSE_STATUS_CHANGE"; sseStatus: SSEStatus; isTerminal: boolean }
  | { type: "START_POLLING" }
  | { type: "STOP_POLLING" }
  | { type: "TERMINAL"; outcome: "completed" | "failed" };

function deriveStatus(state: Omit<ConnectionState, "status">, sseStatus: SSEStatus): RunWorkspaceStatus {
  if (state.phase === "terminal") {
    return state.coreState === "failed" ? "failed" : "completed";
  }
  if (state.phase === "error") {
    return "error";
  }
  if (state.phase === "polling_fallback") {
    return "polling";
  }
  if (state.phase === "streaming" || sseStatus === "connected" || sseStatus === "connecting" || sseStatus === "reconnecting") {
    return "streaming";
  }
  if (state.coreState === "loading") {
    return "loading";
  }
  return "idle";
}

export function connectionReducer(state: ConnectionState, action: ConnectionAction): ConnectionState {
  let nextState = { ...state };

  switch (action.type) {
    case "HYDRATION_START":
      if (state.phase === "terminal") return state; // Ignore if terminal
      nextState = {
        ...INITIAL_CONNECTION_STATE,
        phase: "hydrating",
        coreState: "loading",
      };
      break;

    case "CORE_LOADED":
      if (state.phase === "terminal") return state;
      nextState.coreState = "ready";
      if (action.isTerminal) {
        nextState.phase = "terminal";
      }
      break;

    case "CORE_FAILED":
      if (state.phase === "terminal") return state;
      nextState.phase = "error";
      nextState.coreState = "failed";
      nextState.coreErrorCode = action.code;
      nextState.coreHttpStatus = action.httpStatus;
      nextState.error = action.error;
      break;

    case "RESPONSES_LOADING":
      if (state.phase === "terminal") return state;
      nextState.responsesState = "loading";
      nextState.responsesError = null;
      break;

    case "RESPONSES_LOADED":
      if (state.phase === "terminal") return state;
      nextState.responsesState = action.count > 0 ? "ready" : "empty";
      break;

    case "RESPONSES_FAILED":
      if (state.phase === "terminal") return state;
      if (action.isMismatch) {
        nextState.responsesState = "deployment_mismatch";
        nextState.responsesError = action.error;
      } else {
        nextState.responsesState = "failed";
        nextState.responsesError = action.error;
      }
      break;

    case "TIMELINE_LOADING":
      if (state.phase === "terminal") return state;
      nextState.timelineState = "loading";
      break;

    case "TIMELINE_LOADED":
      if (state.phase === "terminal") return state;
      nextState.timelineState = action.quality === "debate_only" ? "failed" : action.quality === "events_fallback" ? "degraded" : "ready";
      nextState.hydrationQuality = action.quality;
      nextState.timelineError = action.timelineError;
      nextState.eventsError = action.eventsError;
      break;

    case "TIMELINE_FAILED":
      if (state.phase === "terminal") return state;
      nextState.timelineState = "failed";
      break;

    case "SSE_STATUS_CHANGE":
      if (state.phase === "terminal") return state;
      if (action.isTerminal) return state; // Ignore
      
      if (action.sseStatus === "connected") {
        nextState.phase = "streaming";
        nextState.isPollingFallback = false;
      } else if (action.sseStatus === "closed") {
        // SSE failure handled by START_POLLING
      }
      break;

    case "START_POLLING":
      if (state.phase === "terminal") return state;
      nextState.phase = "polling_fallback";
      nextState.isPollingFallback = true;
      break;

    case "STOP_POLLING":
      if (state.phase === "terminal") return state;
      if (nextState.phase === "polling_fallback") {
        nextState.phase = "hydrating";
      }
      nextState.isPollingFallback = false;
      break;

    case "TERMINAL":
      nextState.phase = "terminal";
      // Ensure we mark core as ready/failed properly if we somehow hit terminal
      if (action.outcome === "failed" && state.coreState !== "ready") {
        nextState.coreState = "failed";
      } else {
        nextState.coreState = "ready";
      }
      break;
  }

  // Derive status
  // We pass a dummy 'disconnected' SSEStatus since the reducer shouldn't fully know real-time SSEStatus without an action,
  // but we mostly rely on phase.
  let pseudoSseStatus: SSEStatus = "idle";
  if (nextState.phase === "streaming") pseudoSseStatus = "connected";
  nextState.status = deriveStatus(nextState, pseudoSseStatus);

  return nextState;
}
