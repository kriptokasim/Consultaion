import { describe, it, expect } from "vitest";
import {
  SUCCESSFUL_RUN_STATUSES,
  TERMINAL_RUN_STATUSES,
  isSuccessfulRunStatus,
  isTerminalRunStatus,
  deriveRunPhase,
} from "./status";

describe("run status", () => {
  it("completed_with_warnings is terminal and successful", () => {
    expect(TERMINAL_RUN_STATUSES.has("completed_with_warnings")).toBe(true);
    expect(SUCCESSFUL_RUN_STATUSES.has("completed_with_warnings")).toBe(true);
  });

  it("cancelled is terminal", () => {
    expect(TERMINAL_RUN_STATUSES.has("cancelled")).toBe(true);
    expect(SUCCESSFUL_RUN_STATUSES.has("cancelled")).toBe(false);
  });

  it("failed is terminal", () => {
    expect(TERMINAL_RUN_STATUSES.has("failed")).toBe(true);
  });

  it("completed is terminal and successful", () => {
    expect(TERMINAL_RUN_STATUSES.has("completed")).toBe(true);
    expect(SUCCESSFUL_RUN_STATUSES.has("completed")).toBe(true);
  });

  it("completed_budget is terminal and successful", () => {
    expect(TERMINAL_RUN_STATUSES.has("completed_budget")).toBe(true);
    expect(SUCCESSFUL_RUN_STATUSES.has("completed_budget")).toBe(true);
  });

  it("isSuccessfulRunStatus returns true for successful statuses", () => {
    expect(isSuccessfulRunStatus("completed")).toBe(true);
    expect(isSuccessfulRunStatus("completed_with_warnings")).toBe(true);
    expect(isSuccessfulRunStatus("completed_budget")).toBe(true);
    expect(isSuccessfulRunStatus("success")).toBe(true);
  });

  it("isSuccessfulRunStatus returns false for non-successful", () => {
    expect(isSuccessfulRunStatus("failed")).toBe(false);
    expect(isSuccessfulRunStatus("cancelled")).toBe(false);
    expect(isSuccessfulRunStatus("running")).toBe(false);
    expect(isSuccessfulRunStatus(null)).toBe(false);
    expect(isSuccessfulRunStatus(undefined)).toBe(false);
  });

  it("isTerminalRunStatus returns true for all terminal statuses", () => {
    expect(isTerminalRunStatus("completed")).toBe(true);
    expect(isTerminalRunStatus("completed_with_warnings")).toBe(true);
    expect(isTerminalRunStatus("completed_budget")).toBe(true);
    expect(isTerminalRunStatus("success")).toBe(true);
    expect(isTerminalRunStatus("failed")).toBe(true);
    expect(isTerminalRunStatus("cancelled")).toBe(true);
  });

  it("isTerminalRunStatus returns false for non-terminal", () => {
    expect(isTerminalRunStatus("running")).toBe(false);
    expect(isTerminalRunStatus("queued")).toBe(false);
    expect(isTerminalRunStatus(null)).toBe(false);
  });

  it("deriveRunPhase returns correct phases", () => {
    expect(deriveRunPhase(null, "idle")).toBe("idle");
    expect(deriveRunPhase("cancelled", "idle")).toBe("cancelled");
    expect(deriveRunPhase("failed", "idle")).toBe("failed");
    expect(deriveRunPhase("completed", "idle")).toBe("completed");
    expect(deriveRunPhase("completed_with_warnings", "idle")).toBe("completed");
    expect(deriveRunPhase("queued", "idle")).toBe("creating");
    expect(deriveRunPhase("scheduled", "idle")).toBe("creating");
    expect(deriveRunPhase("running", "collecting_perspectives")).toBe("active");
    expect(deriveRunPhase("running", "synthesizing")).toBe("synthesizing");
    expect(deriveRunPhase("running", "verifying")).toBe("synthesizing");
    expect(deriveRunPhase("running", "perspectives_ready")).toBe("active");
    expect(deriveRunPhase("running", "collecting_perspectives")).toBe("active");
  });
});
