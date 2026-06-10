import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { ExampleReportPreview } from "./ExampleReportPreview";

vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        "landing.exampleReport.title": "Example Decision Report",
        "landing.exampleReport.subtitle": "What you actually get",
      };
      return translations[key] || key;
    },
  }),
}));

describe("ExampleReportPreview", () => {
  it("renders the section title", () => {
    render(<ExampleReportPreview />);
    expect(screen.getByText("Example Decision Report")).toBeInTheDocument();
  });

  it("renders the verdict", () => {
    render(<ExampleReportPreview />);
    expect(screen.getByText("Proceed with a narrow pilot")).toBeInTheDocument();
  });

  it("renders confidence level", () => {
    render(<ExampleReportPreview />);
    expect(screen.getByText("78%")).toBeInTheDocument();
  });

  it("is labeled as Example, not real data", () => {
    render(<ExampleReportPreview />);
    expect(screen.getByText("Example")).toBeInTheDocument();
  });

  it("renders the report title", () => {
    render(<ExampleReportPreview />);
    expect(screen.getByText("Market Entry Decision")).toBeInTheDocument();
  });
});
