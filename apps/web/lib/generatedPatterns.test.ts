import { describe, expect, it } from "vitest";

import {
  GENERATED_SAFETY_PATTERNS,
  GENERATED_SAFETY_PATTERN_VERSION,
  createDetectionPatterns,
  createRedactionPatterns,
} from "./generatedPatterns";


describe("generated safety patterns", () => {
  it("contains deterministic shared metadata without mutable detection flags", () => {
    expect(GENERATED_SAFETY_PATTERN_VERSION).toBe(1);
    expect(GENERATED_SAFETY_PATTERNS.length).toBeGreaterThan(0);
    expect(new Set(GENERATED_SAFETY_PATTERNS.map((pattern) => pattern.name)).size)
      .toBe(GENERATED_SAFETY_PATTERNS.length);
    expect(GENERATED_SAFETY_PATTERNS.every((pattern) => !pattern.detectionFlags.includes("g")))
      .toBe(true);
  });

  it("creates fresh regex instances for detection and redaction", () => {
    const firstDetection = createDetectionPatterns();
    const secondDetection = createDetectionPatterns();
    const redaction = createRedactionPatterns();

    expect(firstDetection[0].regex).not.toBe(secondDetection[0].regex);
    expect(firstDetection.every(({ regex }) => !regex.global)).toBe(true);
    expect(redaction.every(({ regex }) => regex.global)).toBe(true);
  });
});
