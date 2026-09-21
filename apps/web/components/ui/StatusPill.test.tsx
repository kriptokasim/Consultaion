import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { I18nClientProvider } from "@/lib/i18n/I18nClientProvider";
import { getDictionary } from "@/lib/i18n/dictionaries";

import { StatusPill } from "./StatusPill";

describe("StatusPill (canonical New UX)", () => {
  it("renders the four-value status vocabulary in English", () => {
    render(
      <I18nClientProvider locale="en" messages={getDictionary("en")}>
        <StatusPill status="live" />
      </I18nClientProvider>,
    );
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("renders the active locale for needsYou", () => {
    render(
      <I18nClientProvider locale="tr" messages={getDictionary("tr")}>
        <StatusPill status="needsYou" />
      </I18nClientProvider>,
    );
    expect(screen.getByText("Sizi bekliyor")).toBeInTheDocument();
  });
});
