import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PublicRunCTATop, PublicRunCTAFooter } from "./CTABanner";
import React from "react";

// Mock the analytics module
vi.mock("@/lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

describe("CTABanner Components", () => {
  describe("PublicRunCTATop", () => {
    it("renders the top CTA banner with debate run buttons", () => {
      render(<PublicRunCTATop debateId="test-debate-id" />);

      expect(
        screen.getByText("Want to compare models yourself?")
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Run this prompt yourself" })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Create your own run" })
      ).toBeInTheDocument();
    });

    it("triggers event tracking on click", async () => {
      const { trackEvent } = await import("@/lib/analytics");
      render(<PublicRunCTATop debateId="test-debate-id" />);

      const runSameButton = screen.getByRole("link", {
        name: "Run this prompt yourself",
      });
      fireEvent.click(runSameButton);
      expect(trackEvent).toHaveBeenCalledWith(
        "public_run_cta_clicked",
        expect.objectContaining({
          debate_id: "test-debate-id",
          cta_location: "top_banner_run_same",
        })
      );
    });
  });

  describe("PublicRunCTAFooter", () => {
    it("renders the footer CTA banner with debate run buttons", () => {
      render(<PublicRunCTAFooter debateId="test-debate-id" />);

      expect(
        screen.getByText("Want to compare AI models on your own question?")
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Start your own Arena run" })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "See how it works" })
      ).toBeInTheDocument();
    });

    it("triggers event tracking on footer clicks", async () => {
      const { trackEvent } = await import("@/lib/analytics");
      render(<PublicRunCTAFooter debateId="test-debate-id" />);

      const startOwnButton = screen.getByRole("link", {
        name: "Start your own Arena run",
      });
      fireEvent.click(startOwnButton);
      expect(trackEvent).toHaveBeenCalledWith(
        "public_run_cta_clicked",
        expect.objectContaining({
          debate_id: "test-debate-id",
          cta_location: "footer",
          intent: "create_own_run",
        })
      );

      const runSameButton = screen.getByRole("link", {
        name: "Run this prompt yourself",
      });
      fireEvent.click(runSameButton);
      expect(trackEvent).toHaveBeenCalledWith(
        "public_run_cta_clicked",
        expect.objectContaining({
          debate_id: "test-debate-id",
          cta_location: "footer_run_same",
          intent: "run_same_prompt",
        })
      );
    });
  });
});
