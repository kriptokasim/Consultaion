export interface RequestOptions {
    signal?: AbortSignal;
    timeoutMs?: number;
}

export interface DebateConfig {
    agents?: any[]; // refine as needed
    judges?: any[]; // refine as needed
    budget?: {
        max_rounds?: number;
        max_time_seconds?: number;
        max_cost_usd?: number;
        early_stop_delta?: number;
    };
}

export interface PanelConfig {
    seats: any[]; // refine as needed
    engine_version?: string;
}

export type PipelineSubStage =
    | "queued"
    | "models_contacted"
    | "collecting_responses"
    | "perspectives_ready"
    | "scoring"
    | "divergence_analysis"
    | "synthesizing"
    | "verifying"
    | "complete";

export interface StageCheckpointDTO {
    stage_key: string;
    status: "pending" | "running" | "completed" | "failed" | "invalidated";
    attempt: number;
    input_hash?: string;
    output_reference?: string;
    started_at?: string;
    completed_at?: string;
    failed_at?: string;
    error_code?: string;
    error_message?: string;
}

export interface ContinuationDTO {
    id: string;
    status: "requested" | "preflight_passed" | "dispatched" | "running" | "completed" | "failed";
    requested_at?: string;
    preflight_passed_at?: string;
    dispatched_at?: string;
    started_at?: string;
    completed_at?: string;
    failed_at?: string;
    failure_code?: string;
    failure_detail_safe?: string;
    retry_of_continuation_id?: string | null;
    idempotency_key?: string;
}

export interface DebateSummary {
    id: string;
    prompt: string;
    status: 'queued' | 'scheduled' | 'running' | 'completed' | 'failed' | 'completed_budget' | 'perspectives_ready';
    created_at: string;
    updated_at: string;
    user_id?: string;
    team_id?: string;
    model_id?: string;
    score?: number;
    mode?: 'arena' | 'conversation' | 'compare' | 'debate' | 'voting' | 'redteam' | 'oracle' | 'challenge';
    current_stage?: PipelineSubStage;
    stage_checkpoints?: StageCheckpointDTO[];
    continuation_status?: ContinuationDTO["status"];
    continuation_id?: string;
    perspectives_ready_at?: string;
    responses_received?: number;
    models_expected?: number;
    scores_received?: number;
    synthesis_status?: "pending" | "succeeded" | "failed" | "fallback";
    verification_status?: "pending" | "verified" | "unverified" | "failed" | "unavailable";
}

export interface DebateDetail extends DebateSummary {
    config: DebateConfig;
    panel_config?: PanelConfig;
    final_content?: string;
    final_meta?: any;
    participant_errors?: Array<{
        id: string;
        role: string;
        name: string;
        error_type: string;
    }>;
    error_reason?: string;

    // --- P143: Top-level synthesis fields (public + private serializers) ---
    synthesis_report?: any;
    synthesis_success?: boolean;
    synthesis_error?: string;
    fallback_model?: string;
    fallback_reason?: string;
    fallback_response?: any;
    semantic_analysis?: any;
    divergence_breakdown?: any;
    successful_count?: number;
    total_count?: number;
    models?: any[];

    model_warnings?: Array<{
        model_id: string;
        display_name: string;
        provider: string;
        error: string;
    }>;
}

export type Role = "agent" | "critic" | "judge" | "synthesizer";

export interface Member {
    id: string;
    name: string;
    role: Role;
    party?: string;
}

export interface ScoreItem {
    persona: string;
    score: number;
    rationale?: string;
}

export interface VotePayload {
    method: "borda" | "condorcet" | "plurality" | "approval";
    ranking: string[];
}

export interface JudgeScoreEvent {
    type: "score";
    persona: string;
    judge: string;
    score: number;
    rationale?: string;
    at?: string;
    role?: Role;
}

export type JudgeVoteFlow = {
    persona: string;
    judge: string;
    score: number;
    vote: "aye" | "nay";
    at?: string;
};

export interface PairwiseEvent {
    type: "pairwise";
    winner: string;
    loser: string;
    judge?: string;
    user_id?: string;
    category?: string | null;
    at?: string;
}

export type DebateEvent =
    | {
        type: "message";
        round?: number;
        actor?: string;
        role?: Role;
        text?: string;
        at?: string;
        seatId?: string;
        provider?: string;
        model?: string;
    }
    | {
        type: "seat_message"; // Added to handle seat_message type seen in RunDetailClient
        seat_name?: string;
        seat_id?: string;
        content?: string;
        text?: string;
        provider?: string;
        model?: string;
        round?: number;
        at?: string;
    }
    | JudgeScoreEvent
    | PairwiseEvent
    | {
        type: "final";
        actor?: string;
        text?: string;
        at?: string;
        role?: Role;
    }
    | {
        type: "notice";
        text?: string;
        at?: string;
        role?: Role;
    }
    | {
        type: "error"; // Added
        message?: string;
        at?: string;
    }
    | {
        type: "round_started"; // Added
        round?: number;
        at?: string;
    }
    | {
        type: "debate_failed"; // Added
        reason?: string;
        at?: string;
    }
    | {
        type: "conversation_summary";
        text?: string;
        content?: string;
        seat_name?: string;
        at?: string;
    }
    | {
        type: "arena_response";
        model_id?: string;
        display_name?: string;
        provider?: string;
        content?: string;
        logo_url?: string;
        persona_type?: string;
        persona_tagline?: string;
        success?: boolean;
        at?: string;
    }
    | {
        type: "arena_synthesis";
        actor?: string;
        text?: string;
        content?: string;
        role?: Role;
        at?: string;
    }
    | {
        type: "arena_started";
        models?: Array<{
            model_id: string;
            display_name: string;
            provider: string;
            logo_url?: string;
        }>;
        at?: string;
    }
    | {
        type: "pipeline_stage_started";
        debate_id?: string;
        stage?: string;
        attempt?: number;
        at?: string;
        counts?: {
            responses?: number;
            models_expected?: number;
            scores?: number;
        };
    }
    | {
        type: "pipeline_stage_completed";
        debate_id?: string;
        stage?: string;
        attempt?: number;
        at?: string;
    }
    | {
        type: "pipeline_stage_failed";
        debate_id?: string;
        stage?: string;
        attempt?: number;
        error_code?: string;
        at?: string;
    }
    | {
        type: "model_response_started";
        model_id?: string;
        display_name?: string;
        at?: string;
    }
    | {
        type: "model_response_completed";
        model_id?: string;
        display_name?: string;
        at?: string;
    }
    | {
        type: "model_response_failed";
        model_id?: string;
        display_name?: string;
        error?: string;
        at?: string;
    }
    | {
        type: "perspectives_ready";
        debate_id?: string;
        count?: number;
        at?: string;
    }
    | {
        type: "continuation_scheduled";
        debate_id?: string;
        continuation_id?: string;
        at?: string;
    }
    | {
        type: "continuation_started";
        debate_id?: string;
        continuation_id?: string;
        at?: string;
    }
    | {
        type: "decision_report_ready";
        debate_id?: string;
        at?: string;
    }
    | {
        type: "verification_completed";
        debate_id?: string;
        status?: string;
        at?: string;
    }
    // FH100: Streaming lifecycle events
    | {
        type: "model_response_queued";
        response_id?: string;
        model_id?: string;
        display_name?: string;
        at?: string;
    }
    | {
        type: "model_response_connecting";
        response_id?: string;
        model_id?: string;
        display_name?: string;
        provider?: string;
        at?: string;
    }
    | {
        type: "model_response_started";
        response_id?: string;
        model_id?: string;
        display_name?: string;
        provider?: string;
        at?: string;
    }
    | {
        type: "model_response_delta";
        response_id?: string;
        model_id?: string;
        text?: string;
        delta_sequence?: number;
        accumulated_chars?: number;
        at?: string;
    }
    | {
        type: "model_response_persisting";
        response_id?: string;
        model_id?: string;
        provider?: string;
        at?: string;
    }
    | {
        type: "model_response_completed";
        response_id?: string;
        model_id?: string;
        display_name?: string;
        provider?: string;
        at?: string;
    }
    | {
        type: "model_response_failed";
        response_id?: string;
        model_id?: string;
        display_name?: string;
        error?: string;
        error_code?: string;
        at?: string;
    };

export interface LeaderboardEntry {
    persona: string;
    elo: number;
    n_matches: number;
    category?: string;
    description?: string;
}

export interface ApiListResponse<T> {
    items: T[];
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
}

export interface UserParticipationResponse {
  stats: {
    total_interactions: number;
    arena_votes: number;
    debate_steers: number;
    voting_predictions: number;
    redteam_critiques: number;
    oracle_branches: number;
    challenge_pushbacks: number;
  };
  recent_activity: {
    id: number;
    debate_id: string;
    type: string;
    details: Record<string, any>;
    created_at: string;
  }[];
}

// ---------------------------------------------------------------------------
// PR-FH89: Canonical persisted model response contract.
// ---------------------------------------------------------------------------

export type PersistedResponseRole =
  | "arena_response"
  | "seat"
  | "delegate"
  | "candidate"
  | "revised";

export interface PersistedModelResponseMetadata {
  logo_url?: string | null;
  persona_type?: string | null;
  persona_tagline?: string | null;
  attempt_count?: number;
}

export interface PersistedModelResponse {
  id: string;
  debate_id: string;
  response_type: string;
  role: string;
  round: number;
  model_id: string;
  display_name: string;
  provider: string;
  content: string;
  success: boolean;
  error_code: string | null;
  error_message: string | null;
  retryable: boolean;
  created_at: string | null;
  metadata: PersistedModelResponseMetadata;
}

export interface PersistedResponsesSummary {
  expected: number;
  persisted: number;
  successful: number;
  failed: number;
}

export interface PersistedResponsesResponse {
  items: PersistedModelResponse[];
  summary: PersistedResponsesSummary;
}
