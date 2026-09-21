import { describe, expect, it } from "vitest";

import { toUiRunStatus } from "./runStatusUi";

describe("toUiRunStatus", () => {
  it("maps a terminal failure to failed, regardless of other flags", () => {
    expect(toUiRunStatus("failed", { hasReport: true, hasError: true })).toBe("failed");
  });

  it("maps a finished run with a report to closed", () => {
    expect(toUiRunStatus("running", { hasReport: true })).toBe("closed");
    expect(toUiRunStatus("completed")).toBe("closed");
    expect(toUiRunStatus("completed_with_warnings")).toBe("closed");
    expect(toUiRunStatus("cancelled")).toBe("closed");
  });

  it("maps a recoverable error to needsYou", () => {
    expect(toUiRunStatus("running", { hasError: true })).toBe("needsYou");
  });

  it("maps in-progress backend and workspace statuses to live", () => {
    expect(toUiRunStatus("queued")).toBe("live");
    expect(toUiRunStatus("running")).toBe("live");
    expect(toUiRunStatus("streaming")).toBe("live");
    expect(toUiRunStatus("polling")).toBe("live");
  });

  it("defaults unknown/missing statuses to live", () => {
    expect(toUiRunStatus(null)).toBe("live");
    expect(toUiRunStatus(undefined)).toBe("live");
    expect(toUiRunStatus("something_new")).toBe("live");
  });
});
