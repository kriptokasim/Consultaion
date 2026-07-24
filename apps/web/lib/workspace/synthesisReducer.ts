export type SynthesisStateStatus =
  | "idle"
  | "streaming"
  | "provisional"
  | "final"
  | "failed";

export interface SynthesisStreamingState {
  synthesisId: string | null;
  runAttempt: number;
  revision: number;
  status: SynthesisStateStatus;
  text: string;
  report: unknown | null;
  inputHash?: string;
  responseIds: string[];
  successfulCount: number;
  totalCount: number;
  lastDeltaSequence: number;
  provisionalPromoted: boolean;
}
export const INITIAL_SYNTHESIS_STATE: SynthesisStreamingState = {
  synthesisId: null,
  runAttempt: 0,
  revision: -1,
  status: "idle",
  text: "",
  report: null,
  responseIds: [],
  successfulCount: 0,
  totalCount: 0,
  lastDeltaSequence: 0,
  provisionalPromoted: false,
};

export interface SynthesisDeltaPayload {
  synthesis_id?: string;
  response_id?: string;
  run_attempt: number;
  revision: number;
  status: "provisional" | "final";
  text: string;
  delta_sequence: number;
  input_hash?: string;
  response_ids?: string[];
  successful_count?: number;
  total_count?: number;
}

export interface SynthesisSnapshotPayload {
  synthesis_id: string;
  run_attempt: number;
  revision: number;
  status: "provisional" | "final" | "failed";
  content?: string;
  report?: unknown;
  input_hash?: string;
  response_ids?: string[];
  successful_count?: number;
  total_count?: number;
  provisional_promoted?: boolean;
}

export type SynthesisAction =
  | { type: "STARTED"; payload: SynthesisSnapshotPayload }
  | { type: "DELTA"; payload: SynthesisDeltaPayload }
  | { type: "REVISION"; payload: SynthesisSnapshotPayload }
  | { type: "FINALIZED"; payload: SynthesisSnapshotPayload }
  | { type: "RESET" };

function isStale(
  state: SynthesisStreamingState,
  payload: Pick<SynthesisSnapshotPayload, "run_attempt" | "revision">,
): boolean {
  return payload.run_attempt < state.runAttempt
    || (
      payload.run_attempt === state.runAttempt
      && payload.revision < state.revision
    );
}

export function isValidSynthesisDeltaPayload(
  payload: unknown,
): payload is SynthesisDeltaPayload {
  if (!payload || typeof payload !== "object") return false;
  const value = payload as Record<string, unknown>;
  return (
    (typeof value.synthesis_id === "string" || typeof value.response_id === "string")
    && typeof value.run_attempt === "number"
    && typeof value.revision === "number"
    && (value.status === "provisional" || value.status === "final")
    && typeof value.text === "string"
    && typeof value.delta_sequence === "number"
  );
}

function fromSnapshot(
  state: SynthesisStreamingState,
  payload: SynthesisSnapshotPayload,
  status: SynthesisStateStatus,
): SynthesisStreamingState {
  if (isStale(state, payload)) return state;
  return {
    synthesisId: payload.synthesis_id,
    runAttempt: payload.run_attempt,
    revision: payload.revision,
    status,
    text: payload.content ?? state.text,
    report: payload.report ?? state.report,
    inputHash: payload.input_hash,
    responseIds: payload.response_ids ?? [],
    successfulCount: payload.successful_count ?? 0,
    totalCount: payload.total_count ?? 0,
    lastDeltaSequence: status === "streaming" ? state.lastDeltaSequence : 0,
    provisionalPromoted: Boolean(payload.provisional_promoted),
  };
}

export function synthesisReducer(
  state: SynthesisStreamingState,
  action: SynthesisAction,
): SynthesisStreamingState {
  switch (action.type) {
    case "STARTED":
      if (isStale(state, action.payload)) return state;
      return {
        ...fromSnapshot(state, action.payload, "streaming"),
        text: "",
        report: null,
        lastDeltaSequence: 0,
      };
    case "DELTA": {
      const payload = action.payload;
      const synthesisId = payload.synthesis_id || payload.response_id;
      if (!synthesisId || isStale(state, payload)) return state;
      if (
        state.synthesisId === synthesisId
        && payload.delta_sequence <= state.lastDeltaSequence
      ) {
        return state;
      }
      const resetForNewRevision = state.synthesisId !== synthesisId
        || state.runAttempt !== payload.run_attempt
        || state.revision !== payload.revision;
      return {
        synthesisId,
        runAttempt: payload.run_attempt,
        revision: payload.revision,
        status: "streaming",
        text: `${resetForNewRevision ? "" : state.text}${payload.text}`,
        report: resetForNewRevision ? null : state.report,
        inputHash: payload.input_hash,
        responseIds: payload.response_ids ?? state.responseIds,
        successfulCount: payload.successful_count ?? state.successfulCount,
        totalCount: payload.total_count ?? state.totalCount,
        lastDeltaSequence: payload.delta_sequence,
        provisionalPromoted: false,
      };
    }
    case "REVISION":
      return fromSnapshot(
        state,
        action.payload,
        action.payload.status === "failed"
          ? "failed"
          : action.payload.status,
      );
    case "FINALIZED":
      return fromSnapshot(
        state,
        action.payload,
        action.payload.status === "failed" ? "failed" : "final",
      );
    case "RESET":
      return INITIAL_SYNTHESIS_STATE;
    default:
      return state;
  }
}
