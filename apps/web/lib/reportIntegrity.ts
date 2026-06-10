/**
 * Frontend decision report integrity guard.
 * Detects raw JSON leaks, fenced markdown code blocks, or schema-key leakage
 * before rendering reports in the UI.
 */

export function fieldLooksCorrupt(value?: string | null): boolean {
  if (!value) return false;
  const t = String(value).trim();

  // Check if string starts with code fence
  if (t.startsWith("```json") || t.startsWith("```")) {
    return true;
  }

  // Check if starts with a JSON brace and contains schema keys
  if (
    t.startsWith("{") &&
    (t.includes('"verdict"') ||
      t.includes('"executive_summary"') ||
      t.includes('"context_needed"') ||
      t.includes('"unique_insights"') ||
      t.includes('"quality_meta"'))
  ) {
    return true;
  }

  // Check for leakage of multiple schema markers
  const schemaMarkers = [
    '"verdict"',
    '"executive_summary"',
    '"context_needed"',
    '"unique_insights"',
    '"quality_meta"',
    '"risks_and_assumptions"',
  ];

  const markerCount = schemaMarkers.filter((m) => t.includes(m)).length;
  return markerCount >= 2;
}

export function reportContainsRawJsonLeak(report: any): boolean {
  if (!report || typeof report !== "object") return false;

  const checkValue = (val: any): boolean => {
    if (typeof val === "string") {
      return fieldLooksCorrupt(val);
    }
    if (Array.isArray(val)) {
      return val.some(checkValue);
    }
    if (val !== null && typeof val === "object") {
      return Object.values(val).some(checkValue);
    }
    return false;
  };

  return checkValue(report);
}

export function isRenderableDecisionReport(report: any): boolean {
  if (!report || typeof report !== "object") return false;
  if (!report.verdict) return false;

  // Block explicitly unrenderable reports (marked by backend validator)
  if (report.quality_meta?.renderable === false) {
    return false;
  }

  // Block reports containing raw JSON leak in any field
  return !reportContainsRawJsonLeak(report);
}
