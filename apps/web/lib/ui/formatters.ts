/**
 * Presentation formatters for the debate/parliament UI.
 * Maps internal backend enum values to user-friendly strings.
 */

/** Maps raw debate status strings to user-readable labels. */
export function formatStatus(status?: string | null): string {
    if (!status) return "Unknown";
    const map: Record<string, string> = {
        queued: "Queued",
        scheduled: "Scheduled",
        running: "Running",
        completed: "Completed",
        completed_budget: "Completed (budget)",
        failed: "Failed",
        debate_failed: "Failed",
    };
    return map[status] ?? status.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

/** Returns true only for statuses that represent active/live debates. */
export function isLiveStatus(status?: string | null): boolean {
    return status === "running" || status === "queued" || status === "scheduled";
}

/** Maps raw backend event type strings to user-readable labels. */
export function formatEventType(type: string): string {
    const map: Record<string, string> = {
        seat_message: "Seat statement",
        message: "Statement",
        score: "Score update",
        final: "Final synthesis",
        notice: "Notice",
        pairwise: "Pairwise vote",
        round_started: "Round started",
        error: "Error",
        debate_failed: "Debate failed",
    };
    if (map[type]) return map[type];
    // Fallback: capitalise the first letter and replace underscores with spaces
    return type.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

/** Maps a raw model ID (e.g. "anthropic/claude-3-5-sonnet-20240620") to a
 *  short, human-readable provider · model label. Returns undefined when the
 *  ID is absent or unrecognised, so callers can choose not to render anything. */
export function formatModelLabel(modelId?: string | null): string | undefined {
    if (!modelId) return undefined;

    const id = modelId.toLowerCase();

    if (id.startsWith("anthropic/")) {
        if (id.includes("claude-3-5-sonnet")) return "Anthropic · Claude 3.5 Sonnet";
        if (id.includes("claude-3-opus")) return "Anthropic · Claude 3 Opus";
        if (id.includes("claude-3-haiku")) return "Anthropic · Claude 3 Haiku";
        if (id.includes("claude-opus-4")) return "Anthropic · Claude Opus 4";
        return "Anthropic · Claude";
    }

    if (id.startsWith("openai/")) {
        if (id.includes("gpt-4o-mini")) return "OpenAI · GPT-4o mini";
        if (id.includes("gpt-4o")) return "OpenAI · GPT-4o";
        if (id.includes("gpt-4-turbo")) return "OpenAI · GPT-4 Turbo";
        if (id.includes("gpt-4")) return "OpenAI · GPT-4";
        if (id.includes("gpt-3.5")) return "OpenAI · GPT-3.5";
        return "OpenAI";
    }

    if (id.startsWith("google/") || id.startsWith("gemini")) {
        if (id.includes("gemini-1.5-pro")) return "Google · Gemini 1.5 Pro";
        if (id.includes("gemini-1.5-flash")) return "Google · Gemini 1.5 Flash";
        if (id.includes("gemini-2.")) return "Google · Gemini 2";
        return "Google · Gemini";
    }

    if (id.startsWith("meta/") || id.includes("llama")) {
        return "Meta · Llama";
    }

    if (id.startsWith("mistral/")) {
        return "Mistral";
    }

    if (id.startsWith("x-ai/") || id.includes("grok")) {
        return "xAI · Grok";
    }

    // Openrouter wraps provider with a prefix like "openrouter/anthropic/..."
    if (id.startsWith("openrouter/")) {
        return formatModelLabel(modelId.slice("openrouter/".length));
    }

    return undefined;
}
