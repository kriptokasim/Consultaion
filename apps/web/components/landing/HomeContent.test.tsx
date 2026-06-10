import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

// Mock next/image
vi.mock("next/image", () => ({
  __esModule: true,
  default: (props: any) => {
    // eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text
    return <img {...props} />;
  },
}));

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock analytics
vi.mock("@/lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

// Mock runtime config
vi.mock("@/lib/config/runtime", () => ({
  API_ORIGIN: "http://localhost:8000",
}));

// Mock i18n
vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        "landing.hero.title": "One question. Multiple AI perspectives. One decision report.",
        "landing.hero.subtitle": "Consultaion runs structured Arena and Debate workflows.",
        "landing.hero.primaryCta": "Start an Arena Run",
        "landing.hero.secondaryCta": "View Example Report",
        "landing.hero.secondaryHint": "Google sign-in is available.",
        "landing.finalCta.title": "Ready to turn disagreement into a decision?",
        "landing.finalCta.primary": "Start an Arena Run",
        "landing.finalCta.secondary": "View Example Report",
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
        "landing.arenaAtAGlance.title": "Arena at a Glance",
        "landing.arenaAtAGlance.subtitle": "Platform metrics",
        "landing.arenaAtAGlance.metrics.completedRuns": "Completed runs",
        "landing.arenaAtAGlance.metrics.reportsGenerated": "Reports generated",
        "landing.arenaAtAGlance.metrics.activeModels": "Active models",
        "landing.arenaAtAGlance.empty": "Be among the first to generate a decision report.",
        "landing.arenaAtAGlance.error": "Live platform stats will appear after public reports are generated.",
        "landing.exampleReport.title": "Example Decision Report",
        "landing.exampleReport.subtitle": "What you actually get",
        "landing.differentiation.title": "Why not just ask two models yourself?",
        "landing.differentiation.subtitle": "You could paste your question.",
        "landing.useCases.label": "Use Cases",
        "landing.useCases.title": "Built for high-stakes decisions",
        "landing.useCases.subtitle": "Teams use Consultaion when a single model answer is not enough",
        "landing.useCases.strategy.title": "Strategy Decision Review",
        "landing.useCases.strategy.description": "Compare how different AI models evaluate.",
        "landing.useCases.product.title": "Product Requirement Stress Test",
        "landing.useCases.product.description": "Surface conflicting assumptions.",
        "landing.useCases.technical.title": "Technical Architecture Comparison",
        "landing.useCases.technical.description": "Evaluate trade-offs.",
        "landing.useCases.research.title": "Policy & Research Synthesis",
        "landing.useCases.research.description": "Synthesize competing viewpoints.",
        "landing.devs.docs": "Docs & API reference",
        "landing.devs.github": "View source on GitHub",
        "nav.pricing": "Pricing",
        "nav.leaderboard": "Leaderboard",
        "nav.hallOfFame": "Hall of Fame",
        "nav.models": "Models",
        "nav.methodology": "Methodology",
        "footer.terms": "Terms",
        "footer.privacy": "Privacy",
      };
      return translations[key] || key;
    },
  }),
}));

// Mock fetch
beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: false,
    json: () => Promise.resolve(null),
  });
});

// Dynamically import after mocks
import HomeContent from "./HomeContent";

describe("HomeContent", () => {
  it("renders the hero headline", () => {
    render(<HomeContent />);
    expect(
      screen.getByText("One question. Multiple AI perspectives. One decision report.")
    ).toBeInTheDocument();
  });

  it("renders primary and secondary hero CTAs", () => {
    render(<HomeContent />);
    // Primary CTA button
    const primaryButtons = screen.getAllByText("Start an Arena Run");
    expect(primaryButtons.length).toBeGreaterThanOrEqual(1);

    // Secondary CTA button
    const secondaryButtons = screen.getAllByText("View Example Report");
    expect(secondaryButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("renders Parliament image with alt text on desktop", () => {
    render(<HomeContent />);
    const img = screen.getByAltText(
      "A futuristic AI parliament chamber representing multiple AI models participating in a structured decision-making arena."
    );
    expect(img).toBeInTheDocument();
  });

  it("renders the final CTA section", () => {
    render(<HomeContent />);
    expect(
      screen.getByText("Ready to turn disagreement into a decision?")
    ).toBeInTheDocument();
  });

  it("does not render fake testimonials", () => {
    render(<HomeContent />);
    expect(screen.queryByText("Sarah K.")).not.toBeInTheDocument();
    expect(screen.queryByText("James M.")).not.toBeInTheDocument();
    expect(screen.queryByText("Trusted by teams worldwide")).not.toBeInTheDocument();
  });
});
