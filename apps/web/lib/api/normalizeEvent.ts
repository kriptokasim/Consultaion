import type { DebateEvent } from "./types";
import type { TimelineEvent } from "../timeline/types";

/**
 * Shape of a raw SSE / timeline event from the backend.
 * The SSE stream wraps payload inside a `payload` envelope,
 * while the REST `/events` endpoint returns flat objects.
 */
interface RawEvent {
    id?: string;
    type: string;
    payload?: Record<string, unknown>;
    [key: string]: unknown;
}

/**
 * Normalise a raw backend event (SSE envelope or REST shape)
 * into the canonical `DebateEvent` discriminated union used by all
 * frontend components.
 *
 * Calling this once at the API boundary means downstream components
 * never need `as any` casts to access event fields.
 */
export function normalizeEvent(raw: RawEvent): DebateEvent {
    // SSE events wrap data inside `payload`; REST events are flat.
    const flat: Record<string, unknown> = {
        ...raw,
        ...(raw.payload && typeof raw.payload === "object" ? raw.payload : {}),
    };

    const type = (flat.type as string) || "notice";
    const at = (flat.at as string) ?? (flat.ts as string) ?? undefined;

    switch (type) {
        case "seat_message":
            return {
                type: "seat_message",
                seat_name: (flat.seat_name as string) ?? undefined,
                seat_id: (flat.seat_id as string) ?? undefined,
                content: (flat.content as string) ?? (flat.text as string) ?? undefined,
                text: (flat.text as string) ?? (flat.content as string) ?? undefined,
                provider: (flat.provider as string) ?? undefined,
                model: (flat.model as string) ?? undefined,
                round: (flat.round as number) ?? undefined,
                at,
            };

        case "message":
            return {
                type: "message",
                round: (flat.round as number) ?? undefined,
                actor: (flat.actor as string) ?? (flat.seat_name as string) ?? undefined,
                role: (flat.role as DebateEvent & { type: "message" } extends { role?: infer R } ? R : never) ?? undefined,
                text: (flat.text as string) ?? (flat.content as string) ?? undefined,
                at,
                seatId: (flat.seatId as string) ?? (flat.seat_id as string) ?? undefined,
                provider: (flat.provider as string) ?? undefined,
                model: (flat.model as string) ?? undefined,
            };

        case "score":
            return {
                type: "score",
                persona: (flat.persona as string) ?? "",
                judge: (flat.judge as string) ?? "",
                score: Number(flat.score) || 0,
                rationale: (flat.rationale as string) ?? undefined,
                at,
                role: "judge",
            };

        case "pairwise":
            return {
                type: "pairwise",
                winner: (flat.winner as string) ?? "",
                loser: (flat.loser as string) ?? "",
                judge: (flat.judge as string) ?? undefined,
                at,
            };

        case "final":
            return {
                type: "final",
                actor: (flat.actor as string) ?? undefined,
                text: (flat.text as string) ?? (flat.content as string) ?? undefined,
                at,
                role: "synthesizer",
            };

        case "conversation_summary":
            return {
                type: "conversation_summary",
                text: (flat.text as string) ?? (flat.content as string) ?? undefined,
                content: (flat.content as string) ?? (flat.text as string) ?? undefined,
                seat_name: (flat.seat_name as string) ?? undefined,
                at,
            };

        case "round_started":
            return {
                type: "round_started",
                round: (flat.round as number) ?? undefined,
                at,
            };

        case "error":
            return {
                type: "error",
                message: (flat.message as string) ?? (flat.text as string) ?? undefined,
                at,
            };

        case "debate_failed":
            return {
                type: "debate_failed",
                reason: (flat.reason as string) ?? (flat.message as string) ?? undefined,
                at,
            };

        case "arena_response":
            return {
                type: "arena_response",
                model_id: (flat.model_id as string) ?? undefined,
                display_name: (flat.display_name as string) ?? (flat.seat_name as string) ?? undefined,
                provider: (flat.provider as string) ?? undefined,
                content: (flat.content as string) ?? (flat.text as string) ?? undefined,
                logo_url: (flat.logo_url as string) ?? undefined,
                persona_type: (flat.persona_type as string) ?? undefined,
                persona_tagline: (flat.persona_tagline as string) ?? undefined,
                success: (flat.success as boolean) ?? true,
                at,
            };

        case "arena_synthesis":
            return {
                type: "arena_synthesis",
                actor: (flat.actor as string) ?? "Synthesizer",
                text: (flat.text as string) ?? (flat.content as string) ?? undefined,
                content: (flat.content as string) ?? (flat.text as string) ?? undefined,
                role: "synthesizer",
                at,
            };

        case "arena_started":
            return {
                type: "arena_started",
                models: (flat.models as any[]) ?? undefined,
                at,
            };

        case "notice":
        default:
            return {
                type: "notice",
                text: (flat.text as string) ?? (flat.message as string) ?? undefined,
                at,
            };
    }
}

/**
 * Normalise a batch of raw events — convenience wrapper for arrays.
 */
export function normalizeEvents(raw: RawEvent[]): DebateEvent[] {
    return raw.map(normalizeEvent);
}

/**
 * Normalise raw timeline or fallback items into stable TimelineEvents, deduplicating
 * by ID or synthetic stable keys.
 */
export function normalizeTimelineItems(items: unknown[], debateId: string): TimelineEvent[] {
    const events: TimelineEvent[] = [];
    const seenKeys = new Set<string>();

    for (const raw of items as any[]) {
        if (!raw) continue;

        const normalizedPayload = normalizeEvent(raw);
        const ts = raw.ts || raw.at || raw.created_at || new Date().toISOString();
        const type = raw.type || "notice";

        // Stable deduplication key
        let dedupKey = raw.id;
        if (!dedupKey && raw.payload?.id) dedupKey = raw.payload.id;
        if (!dedupKey && type === "arena_response") {
            const modelId = raw.model_id || raw.payload?.model_id || "unknown_model";
            dedupKey = `${type}-${modelId}-${ts}`;
        }
        // Fallback for types without obvious stable IDs
        if (!dedupKey) {
            dedupKey = `${type}-${ts}-${Math.random().toString(36).substring(7)}`;
        }

        if (seenKeys.has(dedupKey)) continue;
        seenKeys.add(dedupKey);

        const event: TimelineEvent = {
            id: dedupKey,
            debate_id: debateId,
            ts,
            type,
            round: raw.round || 0,
            seat: raw.seat,
            payload: normalizedPayload as unknown as Record<string, unknown>,
        };

        events.push(event);
    }

    return events;
}
