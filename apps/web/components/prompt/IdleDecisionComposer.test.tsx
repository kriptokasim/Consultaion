import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { I18nClientProvider } from "@/lib/i18n/I18nClientProvider";
import { getDictionary } from "@/lib/i18n/dictionaries";

import { IdleDecisionComposer } from "./IdleDecisionComposer";

vi.mock("@/hooks/usePromptHistory", () => ({
  usePromptHistory: () => ({ history: [], addToHistory: vi.fn() }),
}));

vi.mock("@/hooks/useVisualViewport", () => ({
  useVisualViewport: () => ({
    viewportHeight: 500,
    viewportWidth: 390,
    offsetTop: 20,
    keyboardInset: 280,
    isKeyboardOpen: true,
    orientation: "portrait",
  }),
}));

describe("IdleDecisionComposer", () => {
  it("localizes the live composer and raises it above the mobile keyboard", () => {
    const { container } = render(
      <I18nClientProvider locale="tr" messages={getDictionary("tr")}>
        <IdleDecisionComposer
          value=""
          onChange={vi.fn()}
          onSubmit={vi.fn()}
          mode="arena"
          onModeChange={vi.fn()}
        />
      </I18nClientProvider>,
    );

    expect(screen.getByText("Arena Modu")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Karar sorunuzu yazın" })).toBeInTheDocument();

    const mobileComposer = container.querySelector(".fixed");
    expect(mobileComposer?.getAttribute("style")).toContain("--keyboard-offset: 280px");
    expect(mobileComposer?.className).toContain("safe-area-inset-bottom");
  });
});
