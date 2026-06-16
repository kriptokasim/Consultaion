import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import RunsTable from "./runs-table";

// Mock dependencies
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/runs",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({
    t: (key: string) => key, // Just return the key
  }),
}));

vi.mock("@/lib/api", () => ({
  getDebates: vi.fn(),
  normalizeRunStatus: (s: string) => s,
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ pushToast: vi.fn() }),
}));

describe("RunsTable Component", () => {
  const mockRuns = [
    {
      id: "run-1",
      prompt: "Test Prompt 1",
      status: "completed",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      user_id: "user-1",
    },
    {
      id: "run-2",
      prompt: "Test Prompt 2",
      status: "running",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      user_id: "user-2",
    },
  ];

  it("renders all API-provided rows when profile is null", () => {
    render(<RunsTable items={mockRuns} teams={[]} profile={null} />);
    
    // Both runs should be visible
    expect(screen.getByText("Test Prompt 1")).toBeInTheDocument();
    expect(screen.getByText("Test Prompt 2")).toBeInTheDocument();
  });

  it("does not show 'mine' scope when profile is unavailable", () => {
    render(<RunsTable items={mockRuns} teams={[]} profile={null} />);
    
    // The only available scope should be "all"
    expect(screen.getByText("runs.scope.all")).toBeInTheDocument();
    expect(screen.queryByText("runs.scope.mine")).not.toBeInTheDocument();
    expect(screen.queryByText("runs.scope.team")).not.toBeInTheDocument();
  });

  it("admin profile sees all three scopes", () => {
    render(
      <RunsTable 
        items={mockRuns} 
        teams={[]} 
        profile={{ id: "admin-1", role: "admin" }} 
      />
    );
    
    expect(screen.getByText("runs.scope.mine")).toBeInTheDocument();
    expect(screen.getByText("runs.scope.team")).toBeInTheDocument();
    expect(screen.getByText("runs.scope.all")).toBeInTheDocument();
  });

  it("member profile sees 'mine' and 'team', but not 'all'", () => {
    render(
      <RunsTable 
        items={mockRuns} 
        teams={[]} 
        profile={{ id: "user-1", role: "member" }} 
      />
    );
    
    expect(screen.getByText("runs.scope.mine")).toBeInTheDocument();
    expect(screen.getByText("runs.scope.team")).toBeInTheDocument();
    expect(screen.queryByText("runs.scope.all")).not.toBeInTheDocument();
  });
});
