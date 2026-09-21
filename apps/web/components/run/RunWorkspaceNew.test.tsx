import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const { replaceMock, startDebateMock, apiRequestMock, registryQueryMock, getWorkspaceMock, debatesQueryMock } = vi.hoisted(() => {
  return {
    replaceMock: vi.fn(),
    startDebateMock: vi.fn(),
    apiRequestMock: vi.fn(),
    registryQueryMock: {
      data: {
        models: [
          { id: "gpt4o-mini", display_name: "GPT-4o Mini", provider: "openai", enabled: true },
          { id: "claude-sonnet", display_name: "Claude 3.5 Sonnet", provider: "anthropic", enabled: true },
          { id: "gemini-2-flash", display_name: "Gemini 2.0 Flash", provider: "gemini", enabled: true },
          { id: "disabled-model", display_name: "Disabled Model", provider: "openai", enabled: false },
        ],
      },
      isLoading: false,
      isError: false,
      error: null as unknown,
    },
    getWorkspaceMock: { current: null as any },
    debatesQueryMock: {
      data: { items: [] as any[] },
      isLoading: false,
      isError: false,
      error: null as unknown,
    },
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => "/new",
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, startDebate: startDebateMock };
});

vi.mock("@/lib/apiClient", () => ({ apiRequest: apiRequestMock }));

vi.mock("@/hooks/useRunWorkspace", () => ({
  useRunWorkspace: () => getWorkspaceMock.current,
}));

vi.mock("@/lib/api/hooks/useModelRegistry", () => ({
  useModelRegistry: () => registryQueryMock,
}));

vi.mock("@/lib/api/hooks/useDebatesList", () => ({
  useDebatesList: () => debatesQueryMock,
}));

import { I18nClientProvider } from "@/lib/i18n/I18nClientProvider";
import { getDictionary } from "@/lib/i18n/dictionaries";
import RunWorkspaceNew from "./RunWorkspaceNew";

function idleWorkspace(overrides: Partial<any> = {}) {
  return {
    debate: null,
    events: [],
    responses: [],
    mergedStreamingResponses: [],
    synthesisState: { status: "idle", text: "", report: null },
    status: "idle",
    sseStatus: "idle",
    error: null,
    isPollingFallback: false,
    ...overrides,
  };
}

function renderWorkspace(initialRunId: string | null = null) {
  return render(
    <I18nClientProvider locale="en" messages={getDictionary("en")}>
      <RunWorkspaceNew initialRunId={initialRunId} />
    </I18nClientProvider>,
  );
}

describe("RunWorkspaceNew", () => {
  beforeEach(() => {
    getWorkspaceMock.current = idleWorkspace();
    startDebateMock.mockReset();
    apiRequestMock.mockReset();
    replaceMock.mockReset();
    debatesQueryMock.data = { items: [] };
  });

  it("renders the composer with models from the real registry, excluding disabled ones", () => {
    renderWorkspace();
    expect(screen.getByText("Put a question to a panel.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /GPT-4o Mini/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Claude 3.5 Sonnet/ })).toBeInTheDocument();
    expect(screen.queryByText("Disabled Model")).not.toBeInTheDocument();
  });

  it("uses the dedicated Oracle composer without a model panel", () => {
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "Oracle" }));
    expect(screen.getByText("One deep-reasoning model for a focused answer.")).toBeInTheDocument();
    expect(screen.getByText("Oracle uses its dedicated reasoning runtime. No model panel is required.")).toBeInTheDocument();
    expect(screen.queryByText("1 / 1")).not.toBeInTheDocument();
  });

  it("starts Oracle through /oracle and restores its auxiliary run URL", async () => {
    apiRequestMock.mockResolvedValue({ session_id: "oracle-123" });
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "Oracle" }));
    fireEvent.change(screen.getByPlaceholderText("Should we…"), { target: { value: "Should we launch the new plan?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send it to the panel" }));

    await waitFor(() => expect(apiRequestMock).toHaveBeenCalledWith(expect.objectContaining({
      method: "POST",
      path: "/oracle",
      body: { prompt: "Should we launch the new plan?" },
    })));
    expect(replaceMock).toHaveBeenCalledWith("/new?oracle=oracle-123");
    expect(startDebateMock).not.toHaveBeenCalled();
  });

  it("shows RedTeam risk lenses instead of a model panel and sends the selected lenses", async () => {
    apiRequestMock.mockResolvedValue({ id: "redteam-123" });
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "RedTeam" }));
    expect(screen.getByText("Review the proposal through risk lenses. RedTeam uses its dedicated adversarial runtime.")).toBeInTheDocument();
    const financial = screen.getByRole("button", { name: "Financial" });
    expect(financial).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(financial);
    fireEvent.change(screen.getByPlaceholderText("Should we…"), { target: { value: "Should we ship this architecture?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send it to the panel" }));

    await waitFor(() => expect(apiRequestMock).toHaveBeenCalledWith(expect.objectContaining({
      method: "POST",
      path: "/redteam",
      body: {
        proposal_text: "Should we ship this architecture?",
        lenses: ["security", "scaling", "compliance", "financial"],
      },
    })));
    expect(replaceMock).toHaveBeenCalledWith("/new?redteam=redteam-123");
    expect(startDebateMock).not.toHaveBeenCalled();
  });

  it("blocks sending and shows the minimum-selection error when the registry has no models yet", () => {
    const originalData = registryQueryMock.data;
    registryQueryMock.data = { models: [] };
    try {
      renderWorkspace();
      fireEvent.change(screen.getByPlaceholderText("Should we…"), { target: { value: "Ship it?" } });
      fireEvent.click(screen.getByRole("button", { name: "Send it to the panel" }));
      expect(screen.getByRole("alert")).toHaveTextContent("Select at least 2 models.");
      expect(startDebateMock).not.toHaveBeenCalled();
    } finally {
      registryQueryMock.data = originalData;
    }
  });

  it("starts a run with seats mapped from the registry (provider -> provider_key) and navigates", async () => {
    startDebateMock.mockResolvedValue({ id: "run-123" });
    renderWorkspace();
    fireEvent.change(screen.getByPlaceholderText("Should we…"), { target: { value: "Ship it?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send it to the panel" }));

    await waitFor(() => expect(startDebateMock).toHaveBeenCalledTimes(1));
    const call = startDebateMock.mock.calls[0][0];
    expect(call.prompt).toBe("Ship it?");
    expect(call.panel_config.seats.length).toBeGreaterThanOrEqual(2);
    expect(call.panel_config.seats[0]).toMatchObject({
      model: "gpt4o-mini",
      provider_key: "openai",
      display_name: "GPT-4o Mini",
    });
    expect(replaceMock).toHaveBeenCalledWith("/new?run=run-123");
  });

  it("shows the loading state instead of model rows while the registry is fetching", () => {
    registryQueryMock.isLoading = true;
    renderWorkspace();
    expect(screen.getByText("Loading the model panel…")).toBeInTheDocument();
    registryQueryMock.isLoading = false;
  });

  it("renders no recent-runs section for a first-time visitor with no run history", () => {
    renderWorkspace();
    expect(screen.queryByText("Recent runs")).not.toBeInTheDocument();
  });

  it("lists a closed run with its real verdict confidence and mode, and prefills the composer on click", () => {
    debatesQueryMock.data = {
      items: [
        {
          id: "run-closed",
          prompt: "Should we expand to Europe?",
          status: "completed",
          mode: "debate",
          verdict: { confidence: 0.82 },
        },
      ],
    };
    renderWorkspace();
    expect(screen.getByText("Recent runs")).toBeInTheDocument();
    expect(screen.getByText("Debate · 82%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Should we expand to Europe?" }));
    expect(screen.getByPlaceholderText("Should we…")).toHaveValue("Should we expand to Europe?");
  });

  it("pins an in-progress run above the composer with a rejoin link, separate from the recent-runs list", () => {
    debatesQueryMock.data = {
      items: [
        { id: "run-live", prompt: "Draft the Q3 roadmap", status: "running", mode: "arena" },
        { id: "run-closed", prompt: "Pick a vendor", status: "completed", mode: "compare", verdict: { confidence: 0.6 } },
      ],
    };
    renderWorkspace();
    expect(screen.getByRole("link", { name: "Rejoin" })).toHaveAttribute("href", "/new?run=run-live");
    // The pinned run's own question text should not also appear in the recent-runs list below it.
    expect(screen.getAllByText("Draft the Q3 roadmap")).toHaveLength(1);
    expect(screen.getByText("Pick a vendor")).toBeInTheDocument();
  });

  it("hydrates the rejoined run mode from the persisted debate", () => {
    getWorkspaceMock.current = idleWorkspace({
      debate: { id: "run-compare", prompt: "Compare these choices", status: "running", mode: "compare" },
      status: "streaming",
      mergedStreamingResponses: [
        { responseId: "r1", modelId: "claude-sonnet", displayName: "Claude 3.5 Sonnet", content: "Claude response", state: "streaming" },
      ],
    });
    renderWorkspace("run-compare");
    expect(screen.getByText("Compare")).toBeInTheDocument();
    expect(screen.getByText("Claude response")).toBeInTheDocument();
    expect(screen.queryByText("Confidence")).not.toBeInTheDocument();
  });

  it("renders the canonical run status pill once a run and debate exist", () => {
    getWorkspaceMock.current = idleWorkspace({
      debate: { id: "run-123", prompt: "Ship it?", status: "running" },
      status: "streaming",
    });
    renderWorkspace("run-123");
    expect(screen.getByText("Ship it?")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
  });
});
