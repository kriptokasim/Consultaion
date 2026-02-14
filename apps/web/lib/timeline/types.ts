import { DebateConfig } from "../api/types";

export interface TimelineEvent {
    id: string;
    debate_id: string;
    ts: string;
    type: string;
    round: number;
    seat?: string;
    payload: Record<string, any>;
}

export interface TimelineState {
    events: TimelineEvent[];
    isRecovering: boolean;
    error: string | null;
    status: string;
    config: DebateConfig | null;
}

export type TimelineAction =
    | { type: "INIT"; events: TimelineEvent[]; status: string; config: DebateConfig }
    | { type: "APPEND"; event: TimelineEvent }
    | { type: "ERROR"; error: string }
    | { type: "SET_STATUS"; status: string }
    | { type: "RESET" };
