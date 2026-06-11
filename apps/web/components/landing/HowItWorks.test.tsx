import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { HowItWorks } from "./HowItWorks";

// Mock scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

// Mock matchMedia
const createMatchMedia = (matches: boolean) =>
  vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));

vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        "landing.howItWorks.title": "How Consultaion turns debate into a decision",
        "landing.howItWorks.subtitle": "From question to decision report",
        "landing.howItWorks.steps.ask.title": "Ask one decision question",
        "landing.howItWorks.steps.ask.description": "Start with one strategic question.",
        "landing.howItWorks.steps.compare.title": "Compare model perspectives",
        "landing.howItWorks.steps.compare.description": "Multiple AI models respond.",
        "landing.howItWorks.steps.divergence.title": "Surface disagreement",
        "landing.howItWorks.steps.divergence.description": "Identifies consensus.",
        "landing.howItWorks.steps.report.title": "Receive a decision report",
        "landing.howItWorks.steps.report.description": "Structured report.",
      };
      return translations[key] || key;
    },
  }),
}));

vi.mock("@/hooks/use-reduced-motion", () => ({
  useReducedMotion: vi.fn(() => false),
}));

// Get the mock so we can change its return value per test
import { useReducedMotion } from "@/hooks/use-reduced-motion";
const mockedUseReducedMotion = vi.mocked(useReducedMotion);

describe("HowItWorks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.matchMedia = createMatchMedia(false);
    mockedUseReducedMotion.mockReturnValue(false);
  });

  it("renders section title", () => {
    render(<HowItWorks />);
    expect(
      screen.getByText("How Consultaion turns debate into a decision")
    ).toBeInTheDocument();
  });

  it("renders all four steps", () => {
    render(<HowItWorks />);
    expect(screen.getAllByText("Ask one decision question").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Compare model perspectives").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Surface disagreement").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Receive a decision report").length).toBeGreaterThanOrEqual(1);
  });

  it("desktop step cards are rendered as buttons", () => {
    render(<HowItWorks />);
    // Desktop layout renders buttons for each step
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThanOrEqual(4);
  });

  it("clicking step 2 sets it active", () => {
    render(<HowItWorks />);
    const buttons = screen.getAllByRole("button");
    // Click the second step button (index 1)
    fireEvent.click(buttons[1]);
    // Check aria-current is set on the clicked button
    expect(buttons[1]).toHaveAttribute("aria-current", "step");
  });

  it("clicking step calls scrollIntoView", () => {
    render(<HowItWorks />);
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[2]);
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it("aria-current is set on active step only", () => {
    render(<HowItWorks />);
    const buttons = screen.getAllByRole("button");
    // Initially step 0 is active
    expect(buttons[0]).toHaveAttribute("aria-current", "step");
    expect(buttons[1]).not.toHaveAttribute("aria-current");
    expect(buttons[2]).not.toHaveAttribute("aria-current");
    expect(buttons[3]).not.toHaveAttribute("aria-current");
  });

  it("reduced motion uses auto scroll behavior", () => {
    mockedUseReducedMotion.mockReturnValue(true);
    render(<HowItWorks />);
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[1]);
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith(
      expect.objectContaining({ behavior: "auto" })
    );
  });

  it("normal motion uses smooth scroll behavior", () => {
    mockedUseReducedMotion.mockReturnValue(false);
    render(<HowItWorks />);
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[1]);
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith(
      expect.objectContaining({ behavior: "smooth" })
    );
  });

  it("progress rail reflects active step", () => {
    const { container } = render(<HowItWorks />);
    // Progress rail is aria-hidden, find by class pattern
    const progressBars = container.querySelectorAll('[aria-hidden="true"] > div');
    // First bar should be amber (active), since step 0 is active by default
    expect(progressBars.length).toBe(4);
    // First bar should have amber class
    expect(progressBars[0].className).toContain("bg-amber-500");
    // Remaining bars should have slate class
    expect(progressBars[1].className).toContain("bg-slate-200");
    expect(progressBars[2].className).toContain("bg-slate-200");
    expect(progressBars[3].className).toContain("bg-slate-200");
  });

  it("progress rail updates when step changes", () => {
    const { container } = render(<HowItWorks />);
    const buttons = screen.getAllByRole("button");

    // Click step 3 (index 2)
    fireEvent.click(buttons[2]);

    const progressBars = container.querySelectorAll('[aria-hidden="true"] > div');
    // Steps 0, 1, 2 should be amber (index <= activeStep)
    expect(progressBars[0].className).toContain("bg-amber-500");
    expect(progressBars[1].className).toContain("bg-amber-500");
    expect(progressBars[2].className).toContain("bg-amber-500");
    // Step 3 should be slate
    expect(progressBars[3].className).toContain("bg-slate-200");
  });

  it("section has correct aria-labelledby", () => {
    const { container } = render(<HowItWorks />);
    const section = container.querySelector("section");
    expect(section).toHaveAttribute("aria-labelledby", "how-it-works-heading");
  });
});
