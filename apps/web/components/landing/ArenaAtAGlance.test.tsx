import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { ArenaAtAGlance } from "./ArenaAtAGlance";

vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        "landing.arenaAtAGlance.title": "Arena at a Glance",
        "landing.arenaAtAGlance.subtitle": "Platform metrics",
        "landing.arenaAtAGlance.metrics.completedRuns": "Completed runs",
        "landing.arenaAtAGlance.metrics.reportsGenerated": "Reports generated",
        "landing.arenaAtAGlance.metrics.activeModels": "Active models",
        "landing.arenaAtAGlance.metrics.averageDivergence": "Avg divergence",
        "landing.arenaAtAGlance.empty": "Be among the first to generate a decision report.",
        "landing.arenaAtAGlance.error": "Live platform stats will appear after public reports are generated.",
      };
      return translations[key] || key;
    },
  }),
}));

vi.mock("@/lib/config/runtime", () => ({
  API_ORIGIN: "http://localhost:8000",
}));

describe("ArenaAtAGlance", () => {
  it("renders fallback on API error", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network error"));
    render(<ArenaAtAGlance />);
    await waitFor(() => {
      expect(
        screen.getByText("Live platform stats will appear after public reports are generated.")
      ).toBeInTheDocument();
    });
  });

  it("renders real data when API returns stats", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          completed_runs: 42,
          reports_generated: 38,
          active_models: 5,
          avg_divergence_score: null,
        }),
    });
    render(<ArenaAtAGlance />);
    await waitFor(() => {
      expect(screen.getByText("Completed runs")).toBeInTheDocument();
      expect(screen.getByText("Reports generated")).toBeInTheDocument();
      expect(screen.getByText("Active models")).toBeInTheDocument();
    });
  });

  it("renders empty state when all stats are zero", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          completed_runs: 0,
          reports_generated: 0,
          active_models: 0,
          avg_divergence_score: null,
        }),
    });
    render(<ArenaAtAGlance />);
    await waitFor(() => {
      expect(
        screen.getByText("Be among the first to generate a decision report.")
      ).toBeInTheDocument();
    });
  });
});
