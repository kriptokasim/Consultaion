import { performance } from "node:perf_hooks";
import { describe, expect, it } from "vitest";

import fixtureContract from "../../../config/safety-pattern-fixtures.json";
import {
  containsSensitivePattern,
  detectSensitiveCategories,
  sanitizePublicText,
} from "./textSafety";


describe("shared safety contract", () => {
  it.each(fixtureContract.fixtures)("matches $name", (fixture) => {
    expect(containsSensitivePattern(fixture.input)).toBe(fixture.expected_sensitive);
    expect(detectSensitiveCategories(fixture.input)).toEqual(fixture.expected_categories);

    const sanitized = sanitizePublicText(fixture.input);
    for (const replacement of fixture.expected_redactions) {
      expect(sanitized).toContain(replacement);
    }
    if (!fixture.expected_sensitive) {
      expect(sanitized).toBe(fixture.input);
    }
  });

  it("requires Luhn validation before redacting a card candidate", () => {
    expect(sanitizePublicText("4111 1111 1111 1111")).toBe("[REDACTED_CC]");
    expect(sanitizePublicText("4111 1111 1111 1112")).toBe("4111 1111 1111 1112");
  });

  it("handles long safe input with bounded runtime", () => {
    const text = "ordinary prose with punctuation. ".repeat(10_000);

    const started = performance.now();
    expect(containsSensitivePattern(text)).toBe(false);

    expect(performance.now() - started).toBeLessThan(1_000);
  });
});
