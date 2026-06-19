import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SafeMarkdown } from "./SafeMarkdown";

describe("SafeMarkdown", () => {
  it("renders basic markdown", () => {
    render(<SafeMarkdown content="# Hello" />);
    expect(screen.getByText("Hello")).toBeTruthy();
  });

  it("renders bold text", () => {
    render(<SafeMarkdown content="**bold**" />);
    expect(screen.getByText("bold")).toBeTruthy();
  });

  it("renders lists", () => {
    render(<SafeMarkdown content="- item 1\n- item 2" />);
    expect(screen.getByText("item 1")).toBeTruthy();
    expect(screen.getByText("item 2")).toBeTruthy();
  });

  it("renders code blocks", () => {
    render(<SafeMarkdown content="```python\nprint('hello')\n```" />);
    expect(screen.getByText(/print/)).toBeTruthy();
  });

  it("sanitizes script tags", () => {
    const { container } = render(
      <SafeMarkdown content="Hello <script>alert('xss')</script> World" />
    );
    expect(container.innerHTML).not.toContain("<script>");
  });

  it("sanitizes event handlers", () => {
    const { container } = render(
      <SafeMarkdown content="[link](javascript:alert('xss'))" />
    );
    expect(container.innerHTML).not.toContain("javascript:");
  });

  it("applies custom className", () => {
    const { container } = render(
      <SafeMarkdown content="text" className="custom" />
    );
    expect(container.querySelector(".custom")).toBeTruthy();
  });

  it("handles empty content", () => {
    const { container } = render(<SafeMarkdown content="" />);
    expect(container.textContent).toBe("");
  });

  it("handles null/undefined gracefully", () => {
    const { container } = render(<SafeMarkdown content={""} />);
    expect(container.textContent).toBe("");
  });

  it("renders blockquotes", () => {
    render(<SafeMarkdown content="> quote" />);
    expect(screen.getByText("quote")).toBeTruthy();
  });

  it("renders tables", () => {
    render(
      <SafeMarkdown content="| A | B |\n|---|---|\n| 1 | 2 |" />
    );
    expect(screen.getByText("A")).toBeTruthy();
  });

  it("preserves link targets safely", () => {
    const { container } = render(
      <SafeMarkdown content="[link](https://example.com)" />
    );
    const link = container.querySelector("a");
    if (link) {
      expect(link.getAttribute("href")).toBe("https://example.com");
    }
  });
});
