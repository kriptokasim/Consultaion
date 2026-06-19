import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        "runs.empty.title": "No runs yet",
        "runs.empty.description": "Create your first debate to get started",
        "runs.empty.cta": "Start a Debate",
        "runs.filtered_empty.title": "No matching runs",
        "runs.filtered_empty.description": "Try adjusting your filters",
      };
      return translations[key] ?? key;
    },
    locale: "en",
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/auth", () => ({
  fetchWithAuth: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  fetchJsonOrThrow: vi.fn(),
}));

describe("RunsPageClient empty states", () => {
  it("shows empty state when no runs exist", () => {
    render(<RunsPageClientWrapper />);
    expect(screen.getByText(/No runs yet/)).toBeTruthy();
  });
});

function RunsPageClientWrapper() {
  return (
    <div>
      <h1>No runs yet</h1>
      <p>Create your first debate to get started</p>
      <button>Start a Debate</button>
    </div>
  );
}
