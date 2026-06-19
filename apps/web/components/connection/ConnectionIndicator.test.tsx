import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConnectionIndicator, type ConnectionStatus } from "./ConnectionIndicator";

describe("ConnectionIndicator", () => {
  it("renders connected status", () => {
    render(<ConnectionIndicator status="connected" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-label");
  });

  it("renders reconnecting status with pulse", () => {
    const { container } = render(<ConnectionIndicator status="reconnecting" />);
    expect(container.querySelector(".animate-pulse")).toBeTruthy();
  });

  it("renders offline status", () => {
    render(<ConnectionIndicator status="offline" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-label");
  });

  it("renders degraded status", () => {
    render(<ConnectionIndicator status="degraded" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-label");
  });

  it("renders closed status", () => {
    render(<ConnectionIndicator status="closed" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-label");
  });

  it("applies custom className", () => {
    const { container } = render(<ConnectionIndicator status="connected" className="ml-4" />);
    expect(container.firstChild).toHaveClass("ml-4");
  });

  it("has accessible role", () => {
    render(<ConnectionIndicator status="connected" />);
    expect(screen.getByRole("status")).toBeTruthy();
  });
});
