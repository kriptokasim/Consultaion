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

function getSeatModelId(seat: unknown): string {
  const s = seat as Record<string, unknown>;
  const candidates = [s.model_id, s.model, s.seat_id];
  return (candidates.find(
    value => typeof value === "string" && value.trim().length > 0
  ) as string | undefined)?.trim() ?? "";
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

export function buildArenaSlots({
  panelSeats,
  finalMetaModels,
  debateModels,
  persistedResponses,
  streamingBuffers,
  fallbackModelIds,
}: {
  panelSeats?: unknown[];
  finalMetaModels?: unknown[];
  debateModels?: unknown[];
  persistedResponses?: PersistedModelResponse[];
  streamingBuffers?: Map<string, StreamingModelBuffer>;
  fallbackModelIds?: string[];
}): ArenaSlot[] {
  const usedModelIds = new Set<string>();
  const slots: ArenaSlot[] = [];

  const persistedByModelId = new Map(
    (persistedResponses ?? []).map((r) => [r.model_id, r])
  );
  const streamingByModelId = new Map<string, StreamingModelBuffer>();
  if (streamingBuffers) {
    Array.from(streamingBuffers.values()).forEach(buf => {
      streamingByModelId.set(buf.modelId, buf);
    });
  }

  // Canonical order: 1. panel_config.seats, 2. final_meta.models, 3. debate.models, 4. fallback
  const orderedModelSources: Array<{ modelId: string; displayName?: string; provider?: string; logoUrl?: string }> = [];

  if (panelSeats && panelSeats.length > 0) {
    for (const seat of panelSeats) {
      const modelId = getSeatModelId(seat);
      if (!modelId || usedModelIds.has(modelId)) continue;
      usedModelIds.add(modelId);
      orderedModelSources.push({
        modelId,
        displayName: getSeatDisplayName(seat) || modelId,
        provider: getSeatProvider(seat),
        logoUrl: getSeatLogoUrl(seat),
      });
    }
  }

  if (finalMetaModels && finalMetaModels.length > 0) {
    for (const m of finalMetaModels) {
      const modelId = typeof m === "string" ? m : (m as Record<string, unknown>).model_id as string;
      if (!modelId || usedModelIds.has(modelId)) continue;
      usedModelIds.add(modelId);
      const obj = typeof m === "object" ? m as Record<string, unknown> : null;
      orderedModelSources.push({
        modelId,
        displayName: (obj?.display_name as string) ?? modelId,
        provider: (obj?.provider as string),
        logoUrl: (obj?.logo_url as string) ?? undefined,
      });
    }
  }

  if (debateModels && debateModels.length > 0) {
    for (const m of debateModels) {
      const modelId = typeof m === "string" ? m : (m as Record<string, unknown>).model_id as string;
      if (!modelId || usedModelIds.has(modelId)) continue;
      usedModelIds.add(modelId);
      const obj = typeof m === "object" ? m as Record<string, unknown> : null;
      orderedModelSources.push({
        modelId,
        displayName: (obj?.display_name as string) ?? modelId,
        provider: (obj?.provider as string),
        logoUrl: (obj?.logo_url as string) ?? undefined,
      });
    }
  }

  // Fallback: when no model metadata exists, use provided fallback IDs
  if (orderedModelSources.length === 0 && fallbackModelIds && fallbackModelIds.length > 0) {
    for (const modelId of fallbackModelIds) {
      if (!modelId || usedModelIds.has(modelId)) continue;
      usedModelIds.add(modelId);
      orderedModelSources.push({ modelId, displayName: modelId });
    }
  }

  // Build ordered slots
  for (const src of orderedModelSources) {
    const persisted = persistedByModelId.get(src.modelId);
    const streaming = streamingByModelId.get(src.modelId);

    let type: ArenaSlot["type"];
    if (persisted) {
      type = "persisted";
    } else if (streaming) {
      type = "streaming";
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
      persisted,
      streaming,
    });
  }

  // Append unexpected model responses (persisted not in ordered list)
  if (persistedResponses) {
    for (const resp of persistedResponses) {
      if (!resp.model_id || usedModelIds.has(resp.model_id)) continue;
      usedModelIds.add(resp.model_id);
      slots.push({
        key: `unexpected-${resp.model_id}`,
        modelId: resp.model_id,
        displayName: resp.display_name || resp.model_id,
        provider: resp.provider,
        type: "persisted",
        persisted: resp,
      });
    }
  }

  // Append unexpected streaming buffers not in ordered list
  if (streamingBuffers) {
    Array.from(streamingBuffers.values()).forEach(buf => {
      if (!buf.modelId || usedModelIds.has(buf.modelId)) return;
      usedModelIds.add(buf.modelId);
      slots.push({
        key: `unexpected-stream-${buf.modelId}`,
        modelId: buf.modelId,
        displayName: buf.displayName || buf.modelId,
        provider: buf.provider,
        type: "streaming",
        streaming: buf,
      });
    });
  }

  return slots;
}
