import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { I18nClientProvider } from "@/lib/i18n/I18nClientProvider";
import { getDictionary } from "@/lib/i18n/dictionaries";

import { PanelPicker, type PanelPickerModel } from "./PanelPicker";

const MODELS: PanelPickerModel[] = [
  { id: "gpt4o", name: "GPT-4o", provider: "OpenAI" },
  { id: "claude", name: "Claude", provider: "Anthropic" },
];

function renderPicker(props: Partial<React.ComponentProps<typeof PanelPicker>> = {}) {
  return render(
    <I18nClientProvider locale="en" messages={getDictionary("en")}>
      <PanelPicker
        models={MODELS}
        selectedIds={["gpt4o"]}
        onToggle={vi.fn()}
        minModels={2}
        maxModels={6}
        {...props}
      />
    </I18nClientProvider>,
  );
}

describe("PanelPicker", () => {
  it("renders one row per model and marks the selected one pressed", () => {
    renderPicker();
    const gpt4o = screen.getByRole("button", { name: /GPT-4o/ });
    const claude = screen.getByRole("button", { name: /Claude/ });
    expect(gpt4o).toHaveAttribute("aria-pressed", "true");
    expect(claude).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onToggle with the model id when a row is clicked", () => {
    const onToggle = vi.fn();
    renderPicker({ onToggle });
    fireEvent.click(screen.getByRole("button", { name: /Claude/ }));
    expect(onToggle).toHaveBeenCalledWith("claude");
  });

  it("shows a loading state instead of rows", () => {
    renderPicker({ isLoading: true });
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /GPT-4o/ })).not.toBeInTheDocument();
  });

  it("shows an error state instead of rows", () => {
    renderPicker({ error: "network down" });
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /GPT-4o/ })).not.toBeInTheDocument();
  });

  it("shows an empty state when the registry has no models", () => {
    renderPicker({ models: [] });
    expect(screen.getByText("No models are available right now.")).toBeInTheDocument();
  });
});
