import { describe, it, expect } from "vitest";
import type { DebateDetail } from "@/lib/api/types";
import { getArenaSynthesisArtifacts } from "./synthesisArtifacts";

/**
 * Minimal DebateDetail factory for testing.
 * Only the fields the normalizer reads need to be present.
 */
function makeDebate(overrides: Partial<DebateDetail> = {}): DebateDetail {
  return {
    id: "test-id",
    prompt: "Test prompt",
    status: "completed",
    mode: "arena",
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
    config: {},
    ...overrides,
  } as DebateDetail;
}

describe("getArenaSynthesisArtifacts", () => {
  // ─── 1. Private shape: final_meta.synthesis_report ─────────────────
  it("extracts report/status/divergence from final_meta (private shape)", () => {
    const debate = makeDebate({
      final_meta: {
        synthesis_report: { title: "Report", verdict: { confidence: 0.8 } },
        synthesis_status: "succeeded",
        divergence_breakdown: { divergence_score: 0.3 },
        fallback_model: "gpt-4o-fallback",
      },
    });

    const a = getArenaSynthesisArtifacts(debate);

    expect(a.synthesisReport).toEqual({ title: "Report", verdict: { confidence: 0.8 } });
    expect(a.synthesisStatus).toBe("succeeded");
    expect(a.divergenceBreakdown).toEqual({ divergence_score: 0.3 });
    expect(a.fallbackModel).toBe("gpt-4o-fallback");
    expect(a.hasStructuredReport).toBe(true);
    expect(a.hasSynthesisOutput).toBe(true);
  });

  // ─── 2. Public shape: top-level fields, no final_meta ──────────────
  it("extracts report/status/divergence from top-level (public shape)", () => {
    const debate = makeDebate({
      synthesis_report: { title: "Public Report" },
      synthesis_status: "succeeded" as any,
      divergence_breakdown: { divergence_score: 0.5 },
      fallback_model: "claude-fallback",
      final_meta: undefined,
    });

    const a = getArenaSynthesisArtifacts(debate);

    expect(a.synthesisReport).toEqual({ title: "Public Report" });
    expect(a.synthesisStatus).toBe("succeeded");
    expect(a.divergenceBreakdown).toEqual({ divergence_score: 0.5 });
    expect(a.fallbackModel).toBe("claude-fallback");
    expect(a.hasStructuredReport).toBe(true);
    expect(a.hasSynthesisOutput).toBe(true);
  });

  // ─── 3. Raw synthesis missing but structured report exists ─────────
  it("flags hasStructuredReport and hasSynthesisOutput when only report exists", () => {
    const debate = makeDebate({
      synthesis_report: { title: "Report Only" },
      final_content: undefined,
    });

    const a = getArenaSynthesisArtifacts(debate);

    expect(a.hasStructuredReport).toBe(true);
    expect(a.hasSynthesisOutput).toBe(true);
    // synthesisText should fallback to something (empty or executive_summary)
    expect(typeof a.synthesisText).toBe("string");
  });

  // ─── 4. Fallback response exists without structured report ─────────
  it("flags hasSynthesisOutput when fallback response exists", () => {
    const debate = makeDebate({
      final_meta: {
        fallback_response: { model: "gpt-4o", content: "Fallback answer" },
        fallback_model: "gpt-4o",
        fallback_reason: "Primary model timed out",
      },
    });

    const a = getArenaSynthesisArtifacts(debate);

    expect(a.hasStructuredReport).toBe(false);
    expect(a.hasSynthesisOutput).toBe(true);
    expect(a.fallbackModel).toBe("gpt-4o");
    expect(a.fallbackReason).toBe("Primary model timed out");
    expect(a.fallbackResponse).toEqual({ model: "gpt-4o", content: "Fallback answer" });
  });

  // ─── 5. Precedence: top-level preferred over final_meta ────────────
  it("prefers top-level fields over final_meta when both exist", () => {
    const debate = makeDebate({
      synthesis_report: { title: "Top-level Report" },
      synthesis_status: "succeeded" as any,
      fallback_model: "top-fallback",
      divergence_breakdown: { divergence_score: 0.1 },
      final_meta: {
        synthesis_report: { title: "Meta Report" },
        synthesis_status: "failed",
        fallback_model: "meta-fallback",
        divergence_breakdown: { divergence_score: 0.9 },
      },
    });

    const a = getArenaSynthesisArtifacts(debate);

    expect(a.synthesisReport).toEqual({ title: "Top-level Report" });
    expect(a.synthesisStatus).toBe("succeeded");
    expect(a.fallbackModel).toBe("top-fallback");
    expect(a.divergenceBreakdown).toEqual({ divergence_score: 0.1 });
  });

  // ─── 6. Empty debate — all flags false ─────────────────────────────
  it("returns empty artifacts for a bare debate with no synthesis data", () => {
    const debate = makeDebate({});

    const a = getArenaSynthesisArtifacts(debate);

    expect(a.synthesisReport).toBeNull();
    expect(a.synthesisStatus).toBeUndefined();
    expect(a.synthesisText).toBe("");
    expect(a.hasStructuredReport).toBe(false);
    expect(a.hasSynthesisOutput).toBe(false);
  });

  // ─── 7. Event synthesis text preferred over final_content ──────────
  it("prefers event synthesis text over final_content", () => {
    const debate = makeDebate({
      final_content: "Persisted final content",
    });

    const a = getArenaSynthesisArtifacts(debate, "Event-derived synthesis text");

    expect(a.synthesisText).toBe("Event-derived synthesis text");
  });

  // ─── 8. final_content used when no event synthesis ─────────────────
  it("falls back to final_content when eventSynthesis is empty", () => {
    const debate = makeDebate({
      final_content: "Persisted final content",
    });

    const a = getArenaSynthesisArtifacts(debate);

    expect(a.synthesisText).toBe("Persisted final content");
    expect(a.hasSynthesisOutput).toBe(true);
  });

  // ─── 9. Executive summary used as last-resort text ─────────────────
  it("uses executive_summary as last-resort synthesisText", () => {
    const debate = makeDebate({
      synthesis_report: {
        title: "Report",
        executive_summary: "Executive summary text",
      },
    });

    const a = getArenaSynthesisArtifacts(debate);

    expect(a.synthesisText).toBe("Executive summary text");
    expect(a.hasSynthesisOutput).toBe(true);
  });

  // ─── 10. synthesis_error propagation ───────────────────────────────
  it("propagates synthesis_error from top-level", () => {
    const debate = makeDebate({
      synthesis_error: "LLM timeout",
    });

    const a = getArenaSynthesisArtifacts(debate);

    expect(a.synthesisError).toBe("LLM timeout");
  });

  // ─── 11. synthesis_error from final_meta fallback ──────────────────
  it("propagates synthesis_error from final_meta when top-level absent", () => {
    const debate = makeDebate({
      final_meta: {
        synthesis_error: "Rate limit exceeded",
      },
    });

    const a = getArenaSynthesisArtifacts(debate);

    expect(a.synthesisError).toBe("Rate limit exceeded");
  });

  // ─── 12. Empty/null report is not renderable ───────────────────────
  it("treats null/empty-object report as non-renderable", () => {
    const nullReport = makeDebate({ synthesis_report: null });
    expect(getArenaSynthesisArtifacts(nullReport).hasStructuredReport).toBe(false);

    const emptyReport = makeDebate({ synthesis_report: {} });
    expect(getArenaSynthesisArtifacts(emptyReport).hasStructuredReport).toBe(false);

    const arrayReport = makeDebate({ synthesis_report: [] as any });
    expect(getArenaSynthesisArtifacts(arrayReport).hasStructuredReport).toBe(false);
  });
});
