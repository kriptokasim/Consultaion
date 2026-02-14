import { TimelineState, TimelineAction, TimelineEvent } from "./types";

export const initialTimelineState: TimelineState = {
    events: [],
    isRecovering: true, // Start in recovering state until initial load
    error: null,
    status: "unknown",
    config: null,
};

export function timelineReducer(
    state: TimelineState,
    action: TimelineAction
): TimelineState {
    switch (action.type) {
        case "INIT": {
            // deduplicate and sort
            const uniqueEvents = new Map<string, TimelineEvent>();
            action.events.forEach((e) => uniqueEvents.set(e.id, e));

            const sorted = Array.from(uniqueEvents.values()).sort(
                (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime()
            );

            return {
                ...state,
                events: sorted,
                status: action.status,
                config: action.config,
                isRecovering: false,
                error: null,
            };
        }

        case "APPEND": {
            // If we already have this event, ignore
            if (state.events.some((e) => e.id === action.event.id)) {
                return state;
            }

            // Check for specific control signals in payloads if any
            // e.g. status changes
            let nextStatus = state.status;
            if (action.event.type === "final") {
                nextStatus = "completed";
            } else if (action.event.type === "error" || action.event.type === "debate_failed") {
                nextStatus = "failed";
            }

            return {
                ...state,
                events: [...state.events, action.event],
                status: nextStatus,
            };
        }

        case "ERROR":
            return { ...state, error: action.error };

        case "SET_STATUS":
            return { ...state, status: action.status };

        case "RESET":
            return initialTimelineState;

        default:
            return state;
    }
}
