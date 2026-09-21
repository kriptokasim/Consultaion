import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { I18nClientProvider } from "@/lib/i18n/I18nClientProvider";
import { getDictionary } from "@/lib/i18n/dictionaries";

import { BroadsheetHero } from "./BroadsheetHero";

describe("BroadsheetHero", () => {
  it("renders exactly one primary CTA (DESIGN-SPEC: hero plus one CTA)", () => {
    render(
      <I18nClientProvider locale="en" messages={getDictionary("en")}>
        <BroadsheetHero />
      </I18nClientProvider>,
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "One question. Multiple AI perspectives. One decision report.",
    );
    const ctas = screen.getAllByRole("link");
    expect(ctas).toHaveLength(1);
    expect(ctas[0]).toHaveTextContent("Start an Arena Run");
  });
});
