import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { I18nClientProvider } from "@/lib/i18n/I18nClientProvider";
import { getDictionary } from "@/lib/i18n/dictionaries";

import StatusPill from "./StatusPill";

describe("StatusPill", () => {
  it("renders the active locale instead of an English fallback", () => {
    render(
      <I18nClientProvider locale="tr" messages={getDictionary("tr")}>
        <StatusPill status="streaming" />
      </I18nClientProvider>,
    );

    expect(screen.getByText("Yanıtlar toplanıyor")).toBeInTheDocument();
  });

  it("preserves an explicit caller-provided label", () => {
    render(
      <I18nClientProvider locale="tr" messages={getDictionary("tr")}>
        <StatusPill status="streaming" label="Özel durum" />
      </I18nClientProvider>,
    );

    expect(screen.getByText("Özel durum")).toBeInTheDocument();
  });
});
