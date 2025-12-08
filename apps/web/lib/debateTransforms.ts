import type { DebateEvent } from "@/components/parliament/types";

export function normalizeLivePayload(payload: any, timestamp: string): DebateEvent[] {
    if (!payload || typeof payload !== "object") return [];
    const type = payload.type;
    if (type === "seat_message") {
        if (!payload.content) return []
        return [
            {
                type: "message" as const,
                actor: payload.seat_name ?? payload.seat_id ?? "Seat",
                role: "agent",
                text: payload.content,
                at: timestamp,
                provider: payload.provider,
                model: payload.model,
                seatId: payload.seat_id,
            },
        ]
    }
    if (type === "message") {
        const entries = Array.isArray(payload.revised) && payload.revised.length
            ? payload.revised
            : Array.isArray(payload.candidates)
                ? payload.candidates
                : [];
        return entries
            .filter((entry: any) => entry && entry.text)
            .map((entry: any) => ({
                type: "message" as const,
                actor: entry.persona ?? entry.role ?? payload.actor,
                role: "agent",
                text: entry.text,
                at: timestamp,
            }));
    }
    if (type === "score") {
        if (Array.isArray(payload.judges) && payload.judges.length) {
            return payload.judges.map((judge: any) => ({
                type: "score" as const,
                persona: judge.persona,
                judge: judge.judge ?? "Panel",
                score: typeof judge.score === "number" ? judge.score : Number(judge.score ?? 0),
                rationale: judge.rationale,
                at: timestamp,
                role: "judge",
            }));
        }
        if (Array.isArray(payload.scores)) {
            return payload.scores.map((score: any) => ({
                type: "score" as const,
                persona: score.persona,
                judge: payload.actor ?? "Panel",
                score: typeof score.score === "number" ? score.score : Number(score.score ?? 0),
                rationale: score.rationale,
                at: timestamp,
                role: "judge",
            }));
        }
    }
    if (type === "final") {
        return [
            {
                type: "final" as const,
                actor: payload.actor ?? "Synthesizer",
                role: "synthesizer",
                text: payload.content ?? payload.meta?.final_content ?? "",
                at: timestamp,
            },
        ];
    }
    if (type === "notice" || type === "error" || type === "round_started") {
        const message =
            payload.message ??
            payload.detail ??
            (type === "round_started" ? `Round ${payload.round ?? ''} started` : undefined);
        if (!message) return [];
        return [
            {
                type: "notice" as const,
                text: message,
                at: timestamp,
                role: "judge",
            },
        ];
    }
    return [];
}
