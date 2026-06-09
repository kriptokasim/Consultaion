import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import ModeSelector from "./ModeSelector";

describe("ModeSelector", () => {
  it("shows only Arena and Debate by default", () => {
    render(<ModeSelector selectedMode="arena" onChange={() => {}} />);
    expect(screen.getByText("Arena")).toBeInTheDocument();
    expect(screen.getByText("Structured Debate")).toBeInTheDocument();
  });

  it("does not show Voting, Red Team, Oracle, or Challenge by default", () => {
    render(<ModeSelector selectedMode="arena" onChange={() => {}} />);
    expect(screen.queryByText("Voting")).not.toBeInTheDocument();
    expect(screen.queryByText("Red Team")).not.toBeInTheDocument();
    expect(screen.queryByText("Oracle")).not.toBeInTheDocument();
    expect(screen.queryByText("Challenge")).not.toBeInTheDocument();
  });

  it("has aria-pressed on selected mode", () => {
    render(<ModeSelector selectedMode="arena" onChange={() => {}} />);
    const arenaButton = screen.getByRole("button", { name: /Select Arena mode/i });
    expect(arenaButton).toHaveAttribute("aria-pressed", "true");
  });

  it("has aria-pressed=false on non-selected mode", () => {
    render(<ModeSelector selectedMode="debate" onChange={() => {}} />);
    const arenaButton = screen.getByRole("button", { name: /Select Arena mode/i });
    expect(arenaButton).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onChange when clicking a mode", () => {
    const handleChange = vi.fn();
    render(<ModeSelector selectedMode="arena" onChange={handleChange} />);
    const debateButton = screen.getByRole("button", { name: /Select Structured Debate mode/i });
    debateButton.click();
    expect(handleChange).toHaveBeenCalledWith("debate");
  });
});
