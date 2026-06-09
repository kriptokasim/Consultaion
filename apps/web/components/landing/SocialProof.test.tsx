import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { SocialProof } from "./SocialProof";

// Mock the i18n hook
vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        "landing.useCases.label": "Use Cases",
        "landing.useCases.title": "Built for high-stakes decisions",
        "landing.useCases.subtitle": "Teams use Consultaion when a single model answer is not enough",
        "landing.useCases.strategy.title": "Strategy Decision Review",
        "landing.useCases.strategy.description": "Compare how different AI models evaluate a strategic pivot.",
        "landing.useCases.product.title": "Product Requirement Stress Test",
        "landing.useCases.product.description": "Surface conflicting assumptions about feature priorities.",
        "landing.useCases.technical.title": "Technical Architecture Comparison",
        "landing.useCases.technical.description": "Evaluate trade-offs across infrastructure choices.",
        "landing.useCases.research.title": "Policy & Research Synthesis",
        "landing.useCases.research.description": "Synthesize competing viewpoints into a structured report.",
      };
      return translations[key] || key;
    },
  }),
}));

describe("SocialProof (Use Cases)", () => {
  it("renders the use cases heading", () => {
    render(<SocialProof />);
    expect(screen.getByText("Built for high-stakes decisions")).toBeInTheDocument();
  });

  it("renders all four use case cards", () => {
    render(<SocialProof />);
    expect(screen.getByText("Strategy Decision Review")).toBeInTheDocument();
    expect(screen.getByText("Product Requirement Stress Test")).toBeInTheDocument();
    expect(screen.getByText("Technical Architecture Comparison")).toBeInTheDocument();
    expect(screen.getByText("Policy & Research Synthesis")).toBeInTheDocument();
  });

  it("renders use case descriptions", () => {
    render(<SocialProof />);
    expect(screen.getByText("Compare how different AI models evaluate a strategic pivot.")).toBeInTheDocument();
  });

  it("does not render any fake testimonials", () => {
    render(<SocialProof />);
    expect(screen.queryByText("Sarah K.")).not.toBeInTheDocument();
    expect(screen.queryByText("James M.")).not.toBeInTheDocument();
    expect(screen.queryByText("Alex R.")).not.toBeInTheDocument();
    expect(screen.queryByText("Strategy Lead")).not.toBeInTheDocument();
    expect(screen.queryByText("Trusted by teams worldwide")).not.toBeInTheDocument();
  });
});
