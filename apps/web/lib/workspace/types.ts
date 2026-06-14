export type WorkspaceStage =
  | "idle"
  | "creating"
  | "contacting_models"
  | "collecting_perspectives"
  | "perspectives_ready"
  | "scoring"
  | "analyzing_divergence"
  | "synthesizing"
  | "verifying"
  | "complete"
  | "degraded"
  | "failed";

export type ModelCardState =
  | "queued"
  | "connecting"
  | "streaming"
  | "complete"
  | "failed";

export interface WorkspaceModelSlot {
  model_id: string;
  display_name: string;
  provider: string;
  logo_url?: string;
  state: ModelCardState;
  content?: string;
}

export interface StageCheckpointInfo {
  stage_key: string;
  status: "pending" | "running" | "completed" | "failed" | "invalidated";
  attempt: number;
  started_at?: string;
  completed_at?: string;
  failed_at?: string;
  error_code?: string;
}

export interface ContinuationInfo {
  status: "requested" | "preflight_passed" | "dispatched" | "running" | "completed" | "failed";
  continuation_id?: string;
  requested_at?: string;
  completed_at?: string;
  failure_code?: string;
  failure_detail_safe?: string;
}

export interface WorkspaceState {
  stage: WorkspaceStage;
  modelSlots: WorkspaceModelSlot[];
  stageCheckpoints: StageCheckpointInfo[];
  continuation: ContinuationInfo | null;
  responsesReceived: number;
  modelsExpected: number;
  scoresReceived: number;
  synthesisStatus: "pending" | "succeeded" | "failed" | "fallback";
  verificationStatus: "pending" | "verified" | "unverified" | "failed" | "unavailable";
  perspectivesReadyAt: string | null;
}
