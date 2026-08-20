import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useVisualViewport } from "./useVisualViewport";

const originalInnerHeight = Object.getOwnPropertyDescriptor(window, "innerHeight");
const originalVisualViewport = Object.getOwnPropertyDescriptor(window, "visualViewport");

afterEach(() => {
  if (originalInnerHeight) Object.defineProperty(window, "innerHeight", originalInnerHeight);
  if (originalVisualViewport) {
    Object.defineProperty(window, "visualViewport", originalVisualViewport);
  } else {
    Reflect.deleteProperty(window, "visualViewport");
  }
});

describe("useVisualViewport", () => {
  it("reports the iOS keyboard inset and clears it when the viewport expands", () => {
    const viewport = new EventTarget() as VisualViewport;
    Object.assign(viewport, {
      height: 500,
      width: 390,
      offsetTop: 20,
    });

    Object.defineProperty(window, "innerHeight", { configurable: true, value: 800 });
    Object.defineProperty(window, "visualViewport", { configurable: true, value: viewport });

    const { result } = renderHook(() => useVisualViewport());

    expect(result.current.keyboardInset).toBe(280);
    expect(result.current.isKeyboardOpen).toBe(true);
    expect(result.current.orientation).toBe("portrait");

    Object.assign(viewport, { height: 760, offsetTop: 0 });
    act(() => viewport.dispatchEvent(new Event("resize")));

    expect(result.current.keyboardInset).toBe(40);
    expect(result.current.isKeyboardOpen).toBe(false);
  });
});
