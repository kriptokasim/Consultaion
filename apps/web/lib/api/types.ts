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

export interface DebateSummary {
    id: string;
    prompt: string;
    status: 'queued' | 'scheduled' | 'running' | 'completed' | 'failed' | 'completed_budget';
    created_at: string;
    updated_at: string;
    user_id?: string;
    team_id?: string;
    model_id?: string;
    score?: number; // derived or from meta
}

export interface DebateDetail extends DebateSummary {
    config: DebateConfig;
    panel_config?: PanelConfig;
    final_content?: string;
    final_meta?: any;
    // Add other fields as needed from the API response
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
        provider?: string;
        model?: string;
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
