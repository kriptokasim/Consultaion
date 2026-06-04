import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PromptPanel } from "./prompt-panel";
import React from "react";

describe("PromptPanel Component", () => {
  it("renders the prompt panel with placeholder text and submit label", () => {
    render(
      <PromptPanel
        value=""
        onChange={() => {}}
        onSubmit={() => {}}
        mode="arena"
      />
    );

    expect(
      screen.getByPlaceholderText(
        "Ask a high-stakes question, compare multiple AI models, and get one synthesized answer..."
      )
    ).toBeInTheDocument();
  });

  it("handles text change event", () => {
    const handleChange = vi.fn();
    render(
      <PromptPanel
        value=""
        onChange={handleChange}
        onSubmit={() => {}}
        mode="arena"
      />
    );

    const textarea = screen.getByPlaceholderText(
      "Ask a high-stakes question, compare multiple AI models, and get one synthesized answer..."
    );
    fireEvent.change(textarea, { target: { value: "New prompt" } });
    expect(handleChange).toHaveBeenCalledWith("New prompt");
  });

  it("calls onSubmit when the button is clicked and input is present", () => {
    const handleSubmit = vi.fn();
    render(
      <PromptPanel
        value="My prompt content"
        onChange={() => {}}
        onSubmit={handleSubmit}
        mode="arena"
      />
    );

    const runButton = screen.getByRole("button", { name: "Run Arena" });
    expect(runButton).toBeEnabled();
    fireEvent.click(runButton);
    expect(handleSubmit).toHaveBeenCalledTimes(1);
  });

  it("disables the run button when value is empty", () => {
    render(
      <PromptPanel
        value=""
        onChange={() => {}}
        onSubmit={() => {}}
        mode="arena"
      />
    );

    const runButton = screen.getByRole("button", { name: "Run Arena" });
    expect(runButton).toBeDisabled();
  });

  it("triggers mode change when clicking mode buttons", () => {
    const handleModeChange = vi.fn();
    render(
      <PromptPanel
        value=""
        onChange={() => {}}
        onSubmit={() => {}}
        mode="arena"
        onModeChange={handleModeChange}
      />
    );

    const debateButton = screen.getByRole("button", { name: "Debate" });
    fireEvent.click(debateButton);
    expect(handleModeChange).toHaveBeenCalledWith("debate");
  });
});
