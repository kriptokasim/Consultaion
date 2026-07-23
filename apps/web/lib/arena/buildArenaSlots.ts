import type { PersistedModelResponse } from "@/lib/api/types";
import type { StreamingModelBuffer, ModelState } from "@/lib/streaming/types";

export interface ArenaSlot {
  key: string;
  modelId: string;
  displayName: string;
  provider?: string;
  logoUrl?: string;
  type: "persisted" | "streaming" | "placeholder";
  persisted?: PersistedModelResponse;
  streaming?: StreamingModelBuffer;
}

const MODEL_ID_ALIASES: Record<string, string> = {
  "gpt-4o-mini": "gpt4o-mini",
  "openai/gpt-4o-mini": "gpt4o-mini",
  "gpt-4o": "gpt4o-deep",
  "openai/gpt-4o": "gpt4o-deep",
  "claude-3-5-sonnet": "claude-sonnet",
  "anthropic/claude-3-5-sonnet-20240620": "claude-sonnet",
  "claude-3-5-haiku": "claude-haiku",
  "anthropic/claude-3-haiku-20240307": "claude-haiku",
  "gemini-1.5-flash": "gemini-2-flash",
  "gemini/gemini-2.0-flash": "gemini-2-flash",
  "gemini-1.5-pro": "gemini-2-5-pro",
  "gemini/gemini-2.5-pro-preview-06-05": "gemini-2-5-pro",
};

export function canonicalizeArenaModelId(modelId: string): string {
  const trimmed = modelId.trim();
  return MODEL_ID_ALIASES[trimmed] ?? trimmed;
}

type ResponseIdentity = {
  responseId: string;
  runAttempt: number;
  retryGeneration: number;
};

function responseIdentity(
  responseId: string | undefined,
  runAttempt?: number,
  retryGeneration?: number,
): ResponseIdentity {
  const id = responseId ?? "";
  const encoded = id.match(/-a(\d+)-g(\d+)-/);
  return {
    responseId: id,
    runAttempt: runAttempt ?? Number(encoded?.[1] ?? 0),
    retryGeneration: retryGeneration ?? Number(encoded?.[2] ?? 0),
  };
}

function compareResponseIdentity(left: ResponseIdentity, right: ResponseIdentity): number {
  return (
    left.runAttempt - right.runAttempt ||
    left.retryGeneration - right.retryGeneration ||
    left.responseId.localeCompare(right.responseId)
  );
}

function persistedIdentity(response: PersistedModelResponse): ResponseIdentity {
  return responseIdentity(
    response.response_id || response.id,
    response.metadata?.run_attempt,
    response.metadata?.retry_generation,
  );
}

function streamingIdentity(buffer: StreamingModelBuffer): ResponseIdentity {
  return responseIdentity(buffer.responseId);
}

function getSeatModelId(seat: unknown): string {
  const s = seat as Record<string, unknown>;
  const candidates = [s.model_id, s.model, s.seat_id];
  const modelId = (candidates.find(
    value => typeof value === "string" && value.trim().length > 0
  ) as string | undefined)?.trim() ?? "";
  return canonicalizeArenaModelId(modelId);
}

function getSeatDisplayName(seat: unknown): string {
  const s = seat as Record<string, unknown>;
  return (s.display_name as string) ?? (s.model as string) ?? "";
}

function getSeatProvider(seat: unknown): string {
  const s = seat as Record<string, unknown>;
  return (s.provider_key as string) ?? (s.provider as string) ?? "";
}

function getSeatLogoUrl(seat: unknown): string | undefined {
  const s = seat as Record<string, unknown>;
  return (s.logo_url as string) ?? undefined;
}

function getModelSource(model: unknown): {
  modelId: string;
  displayName?: string;
  provider?: string;
  logoUrl?: string;
} | null {
  if (typeof model === "string") {
    const modelId = canonicalizeArenaModelId(model);
    return modelId ? { modelId, displayName: modelId } : null;
  }
  if (!model || typeof model !== "object") return null;
  const obj = model as Record<string, unknown>;
  const rawModelId = obj.model_id ?? obj.model ?? obj.seat_id;
  if (typeof rawModelId !== "string" || !rawModelId.trim()) return null;
  return {
    modelId: canonicalizeArenaModelId(rawModelId),
    displayName: (obj.display_name as string) ?? rawModelId,
    provider: (obj.provider as string) ?? (obj.provider_key as string),
    logoUrl: (obj.logo_url as string) ?? undefined,
  };
}

export function buildArenaSlots({
  executionModels,
  panelSeats,
  finalMetaModels,
  debateModels,
  persistedResponses,
  streamingBuffers,
  fallbackModelIds,
}: {
  executionModels?: unknown[];
  panelSeats?: unknown[];
  finalMetaModels?: unknown[];
  debateModels?: unknown[];
  persistedResponses?: PersistedModelResponse[];
  streamingBuffers?: Map<string, StreamingModelBuffer>;
  fallbackModelIds?: string[];
}): ArenaSlot[] {
  const usedModelIds = new Set<string>();
  const slots: ArenaSlot[] = [];

  const persistedByModelId = new Map<string, PersistedModelResponse>();
  for (const response of persistedResponses ?? []) {
    if (!response.model_id) continue;
    const modelId = canonicalizeArenaModelId(response.model_id);
    const current = persistedByModelId.get(modelId);
    if (!current || compareResponseIdentity(persistedIdentity(response), persistedIdentity(current)) > 0) {
      persistedByModelId.set(modelId, response);
    }
  }
  const streamingByModelId = new Map<string, StreamingModelBuffer>();
  if (streamingBuffers) {
    Array.from(streamingBuffers.values()).forEach(buf => {
      const modelId = canonicalizeArenaModelId(buf.modelId);
      const current = streamingByModelId.get(modelId);
      if (!current || compareResponseIdentity(streamingIdentity(buf), streamingIdentity(current)) > 0) {
        streamingByModelId.set(modelId, buf);
      }
    });
  }

  // Pick exactly one authoritative manifest. Mixing panel and executed model
  // lists is what previously left a placeholder beside the real response.
  const orderedModelSources: Array<{ modelId: string; displayName?: string; provider?: string; logoUrl?: string }> = [];
  let authoritativeModels: unknown[] = [];
  let sourceKind: "models" | "panel" = "models";
  if (executionModels?.length) {
    authoritativeModels = executionModels;
  } else if (finalMetaModels?.length) {
    authoritativeModels = finalMetaModels;
  } else if (panelSeats?.length) {
    authoritativeModels = panelSeats;
    sourceKind = "panel";
  } else if (debateModels?.length) {
    authoritativeModels = debateModels;
  } else if (fallbackModelIds?.length) {
    authoritativeModels = fallbackModelIds;
  }

  for (const model of authoritativeModels) {
    const source = sourceKind === "panel"
      ? {
          modelId: getSeatModelId(model),
          displayName: getSeatDisplayName(model),
          provider: getSeatProvider(model),
          logoUrl: getSeatLogoUrl(model),
        }
      : getModelSource(model);
    if (!source?.modelId || usedModelIds.has(source.modelId)) continue;
    usedModelIds.add(source.modelId);
    orderedModelSources.push(source);
  }

  // Build ordered slots
  for (const src of orderedModelSources) {
    const persisted = persistedByModelId.get(src.modelId);
    const streaming = streamingByModelId.get(src.modelId);
    const streamingIsNewer = Boolean(
      persisted &&
      streaming &&
      compareResponseIdentity(streamingIdentity(streaming), persistedIdentity(persisted)) > 0
    );

    let type: ArenaSlot["type"];
    if (streaming && (!persisted || streamingIsNewer)) {
      type = "streaming";
    } else if (persisted) {
      type = "persisted";
    } else {
      type = "placeholder";
    }

    // Prefer persisted response metadata over source metadata
    slots.push({
      key: `model-${src.modelId}`,
      modelId: src.modelId,
      displayName: persisted?.display_name || streaming?.displayName || src.displayName || src.modelId,
      provider: persisted?.provider || streaming?.provider || src.provider,
      logoUrl: persisted?.metadata?.logo_url || src.logoUrl,
      type,
      persisted: type === "persisted" ? persisted : undefined,
      streaming: type === "streaming" ? streaming : undefined,
    });
  }

  // Append unexpected model responses (persisted not in ordered list)
  if (persistedResponses) {
    for (const resp of persistedResponses) {
      const modelId = canonicalizeArenaModelId(resp.model_id || "");
      if (!modelId || usedModelIds.has(modelId)) continue;
      usedModelIds.add(modelId);
      slots.push({
        key: `unexpected-${modelId}`,
        modelId,
        displayName: resp.display_name || modelId,
        provider: resp.provider,
        type: "persisted",
        persisted: resp,
      });
    }
  }

  // Append unexpected streaming buffers not in ordered list
  if (streamingBuffers) {
    Array.from(streamingBuffers.values()).forEach(buf => {
      const modelId = canonicalizeArenaModelId(buf.modelId);
      if (!modelId || usedModelIds.has(modelId)) return;
      usedModelIds.add(modelId);
      slots.push({
        key: `unexpected-stream-${modelId}`,
        modelId,
        displayName: buf.displayName || modelId,
        provider: buf.provider,
        type: "streaming",
        streaming: buf,
      });
    });
  }

  return slots;
}
