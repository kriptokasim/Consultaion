import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";

import { I18nClientProvider } from "@/lib/i18n/I18nClientProvider";
import { getDictionary } from "@/lib/i18n/dictionaries";

import { ModelRegistrySurface } from "./ModelRegistrySurface";

function renderSurface(props: Partial<React.ComponentProps<typeof ModelRegistrySurface>> = {}) {
  return render(
    <I18nClientProvider locale="en" messages={getDictionary("en")}>
      <ModelRegistrySurface modelStats={[]} leaderboard={[]} hallOfFame={[]} {...props} />
    </I18nClientProvider>,
  );
}

describe("ModelRegistrySurface", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("defaults to the Models tab with its empty state", () => {
    renderSurface();
    expect(screen.getByRole("tab", { name: "Models", selected: true })).toBeInTheDocument();
    expect(screen.getByText(/No model stats yet/)).toBeInTheDocument();
  });

  it("reads the initial tab from the URL hash", () => {
    window.location.hash = "#hall-of-fame";
    renderSurface();
    expect(screen.getByRole("tab", { name: "Hall of fame", selected: true })).toBeInTheDocument();
    expect(screen.getByText(/No hall of fame runs yet/)).toBeInTheDocument();
  });

  it("switches tabs on click and updates the hash", () => {
    renderSurface();
    fireEvent.click(screen.getByRole("tab", { name: "Leaderboard" }));
    expect(screen.getByRole("tab", { name: "Leaderboard", selected: true })).toBeInTheDocument();
    expect(screen.getByText(/Leaderboard is warming up/)).toBeInTheDocument();
    expect(window.location.hash).toBe("#leaderboard");
  });

  it("renders real model stats rows, not placeholder data", () => {
    renderSurface({
      modelStats: [{ model: "gpt-4o", total_debates: 12, wins: 8, win_rate: 0.6667, avg_champion_score: 8.4 }],
    });
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
    expect(screen.getByText("66.7%")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("8.40")).toBeInTheDocument();
  });

  it("renders real hall-of-fame cards", () => {
    window.location.hash = "#hall-of-fame";
    renderSurface({
      hallOfFame: [
        { id: "run-1", prompt: "Should we ship v2?", champion: "Claude", champion_score: 9.1, champion_excerpt: "Ship it." },
      ],
    });
    expect(screen.getByText("Claude")).toBeInTheDocument();
    expect(screen.getByText("Should we ship v2?")).toBeInTheDocument();
    expect(screen.getByText("Ship it.")).toBeInTheDocument();
  });
});
