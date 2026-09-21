import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const { replaceMock, startDebateMock, registryQueryMock, getWorkspaceMock } = vi.hoisted(() => {
  return {
    replaceMock: vi.fn(),
    startDebateMock: vi.fn(),
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

vi.mock("@/hooks/useRunWorkspace", () => ({
  useRunWorkspace: () => getWorkspaceMock.current,
}));

vi.mock("@/lib/api/hooks/useModelRegistry", () => ({
  useModelRegistry: () => registryQueryMock,
}));

import { I18nClientProvider } from "@/lib/i18n/I18nClientProvider";
import { getDictionary } from "@/lib/i18n/dictionaries";
import RunWorkspaceNew from "./RunWorkspaceNew";

function idleWorkspace(overrides: Partial<any> = {}) {
  return {
    debate: null,
    events: [],
    responses: [],
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
    replaceMock.mockReset();
  });

  it("renders the composer with models from the real registry, excluding disabled ones", () => {
    renderWorkspace();
    expect(screen.getByText("Put a question to a panel.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /GPT-4o Mini/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Claude 3.5 Sonnet/ })).toBeInTheDocument();
    expect(screen.queryByText("Disabled Model")).not.toBeInTheDocument();
  });

  it("switches the mode blurb when a mode chip is clicked and drops to one model for Oracle", () => {
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "Oracle" }));
    expect(screen.getByText("One deep-reasoning model for a focused answer.")).toBeInTheDocument();
    // Oracle's panelSize is [1, 1]; the picker head shows "n / 1".
    expect(screen.getByText("1 / 1")).toBeInTheDocument();
  });

  it("a toggle can never drop the panel below the active mode's minimum", () => {
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "Oracle" }));
    const onlySeat = screen.getByRole("button", { name: /GPT-4o Mini/ });
    expect(onlySeat).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(onlySeat); // attempt to deselect the only seat in a 1-model mode
    expect(onlySeat).toHaveAttribute("aria-pressed", "true"); // toggle refuses to go below minModels
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
