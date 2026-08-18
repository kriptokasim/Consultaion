import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ParliamentHome from "./ParliamentHome";

const members = [
  { id: "m1", name: "Model One", role: "agent" as const, party: "openai" },
];

describe("ParliamentHome Ask a question CTA", () => {
  beforeEach(() => {
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
  });

  it("invokes the parent hook and focuses the composer textarea", () => {
    const onStart = vi.fn();
    const scrollIntoView = vi.fn();

    render(
      <>
        <ParliamentHome members={members} onStart={onStart} running={false} />
        <textarea aria-label="Decision question" />
      </>,
    );

    const textarea = screen.getByRole("textbox", { name: "Decision question" }) as HTMLTextAreaElement;
    Object.defineProperty(textarea, "scrollIntoView", {
      value: scrollIntoView,
      configurable: true,
    });
    const focusSpy = vi.spyOn(textarea, "focus");

    fireEvent.click(screen.getByRole("button", { name: "Run AI Arena session" }));

    expect(onStart).toHaveBeenCalledTimes(1);
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "center" });
    expect(focusSpy).toHaveBeenCalledTimes(1);
  });

  it("is disabled while an Arena run is active", () => {
    render(<ParliamentHome members={members} running={true} />);
    expect(screen.getByRole("button", { name: "Run AI Arena session" })).toBeDisabled();
  });
});
