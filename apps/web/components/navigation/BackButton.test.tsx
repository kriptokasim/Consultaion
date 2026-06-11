import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

const mockBack = vi.fn();
const mockPush = vi.fn();

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    back: mockBack,
    push: mockPush,
  }),
}));

// Mock next-view-transitions
vi.mock("next-view-transitions", () => ({
  Link: ({ href, children, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import BackButton from "./BackButton";

describe("BackButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders with custom label", () => {
    render(<BackButton label="Go Back" />);
    expect(screen.getByText("Go Back")).toBeInTheDocument();
  });

  it("calls custom onClick when provided", () => {
    const handleClick = vi.fn();
    render(<BackButton label="Go Back" onClick={handleClick} />);
    
    const button = screen.getByRole("button");
    fireEvent.click(button);
    
    expect(handleClick).toHaveBeenCalledTimes(1);
    expect(mockBack).not.toHaveBeenCalled();
  });

  it("calls router.back when no custom onClick is provided", () => {
    render(<BackButton label="Go Back" />);
    
    const button = screen.getByRole("button");
    fireEvent.click(button);
    
    expect(mockBack).toHaveBeenCalledTimes(1);
  });

  it("renders as a Link if href is provided", () => {
    render(<BackButton label="Go Home" href="/home" />);
    
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/home");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
