/**
 * Patchset 143: Canonical frontend normalizer for Arena synthesis artifacts.
 *
 * Problem: The backend public serializer exposes synthesis metadata at top-level
 * (synthesis_report, synthesis_status, fallback_model, etc.), while the private
 * serializer puts them inside final_meta. The frontend inconsistently reads from
 * one or the other, causing public/shared runs to lose report data.
 *
 * Solution: This normalizer reads from both sources with deterministic precedence
 * and produces one canonical shape for all consumers.
 *
 * Precedence: top-level fields first, then final_meta fallback.
 * Rationale: top-level fields are populated by BOTH public and private serializers
 * (private mirrors them as of P143). final_meta is only available to owner/admin.
 */

import type { DebateDetail } from "@/lib/api/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ArenaSynthesisArtifacts {
  /** Best available raw synthesis text for display */
  synthesisText: string;
  /** Structured report object, if available */
  synthesisReport: any | null;
  /** Synthesis pipeline status */
  synthesisStatus?: "pending" | "succeeded" | "failed" | "fallback";
  /** Error message from synthesis pipeline */
  synthesisError?: string;
  /** Model used for fallback when primary synthesis failed */
  fallbackModel?: string;
  /** Reason for fallback */
  fallbackReason?: string;
  /** Full fallback response object */
  fallbackResponse?: { model?: string; content?: string } | null;
  /** Divergence/alignment breakdown data */
  divergenceBreakdown?: any | null;
  /** True if a renderable structured report object exists */
  hasStructuredReport: boolean;
  /** True if any synthesis output is available (raw text, structured report, or fallback) */
  hasSynthesisOutput: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Pick the first defined (non-null, non-undefined) value from candidates.
 */
function pickFirst<T>(...candidates: (T | null | undefined)[]): T | undefined {
  for (const c of candidates) {
    if (c !== null && c !== undefined) return c;
  }
  return undefined;
}

/**
 * Check if a value is a non-null, non-empty object (i.e. a renderable report).
 */
function isRenderableReport(val: unknown): val is Record<string, unknown> {
  return (
    val !== null &&
    val !== undefined &&
    typeof val === "object" &&
    !Array.isArray(val) &&
    Object.keys(val as Record<string, unknown>).length > 0
  );
}

// ---------------------------------------------------------------------------
// Main normalizer
// ---------------------------------------------------------------------------

/**
 * Normalize Arena synthesis artifacts from a DebateDetail object.
 *
 * Merges top-level fields (available in both public and private serializations)
 * with final_meta fields (private/owner only), preferring top-level when present.
 *
 * @param debate - The debate detail object from the API
 * @param eventSynthesis - Optional raw synthesis text derived from SSE/timeline events
 * @returns Canonical ArenaSynthesisArtifacts
 */
export function getArenaSynthesisArtifacts(
  debate: DebateDetail,
  eventSynthesis?: string,
): ArenaSynthesisArtifacts {
  const meta = debate.final_meta ?? {};

  // --- Structured report: top-level first, then final_meta ---
  const synthesisReport =
    pickFirst(debate.synthesis_report, meta.synthesis_report) ?? null;

  // --- Status / error ---
  const synthesisStatus = pickFirst(
    debate.synthesis_status,
    meta.synthesis_status,
  ) as ArenaSynthesisArtifacts["synthesisStatus"];

  const synthesisError = pickFirst(
    debate.synthesis_error,
    meta.synthesis_error,
  ) as string | undefined;

  // --- Fallback fields ---
  const fallbackModel = pickFirst(
    debate.fallback_model,
    meta.fallback_model,
  ) as string | undefined;

  const fallbackReason = pickFirst(
    debate.fallback_reason,
    meta.fallback_reason,
  ) as string | undefined;

  const fallbackResponse = pickFirst(
    debate.fallback_response,
    meta.fallback_response,
  ) as ArenaSynthesisArtifacts["fallbackResponse"];

  // --- Divergence ---
  const divergenceBreakdown = pickFirst(
    debate.divergence_breakdown,
    meta.divergence_breakdown,
  ) ?? null;

  // --- Synthesis text resolution (ordered preference) ---
  let synthesisText = "";

  // 1. Event-derived synthesis text (most reliable for live/recent runs)
  if (eventSynthesis) {
    synthesisText = eventSynthesis;
  }
  // 2. debate.final_content (persisted synthesis text)
  else if (debate.final_content) {
    synthesisText = debate.final_content;
  }
  // 3. Executive summary from structured report (last-resort display text)
  else if (isRenderableReport(synthesisReport) && (synthesisReport as any).executive_summary) {
    synthesisText = (synthesisReport as any).executive_summary;
  }

  // --- Boolean flags ---
  const hasStructuredReport = isRenderableReport(synthesisReport);
  const hasSynthesisOutput =
    !!synthesisText ||
    hasStructuredReport ||
    !!fallbackResponse;

  return {
    synthesisText,
    synthesisReport,
    synthesisStatus,
    synthesisError,
    fallbackModel,
    fallbackReason,
    fallbackResponse,
    divergenceBreakdown,
    hasStructuredReport,
    hasSynthesisOutput,
  };
}
