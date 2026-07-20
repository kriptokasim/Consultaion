/**
 * Sensitive text detection and redaction for public metadata, previews, and analytics.
 * 
 * Frontend equivalent of the backend utils/text_safety.py module.
 * Used for:
 * - OG metadata generation in Next.js generateMetadata
 * - Public run title previews
 * - Analytics event payloads (prevent prompt leakage)
 */

import {
  createDetectionPatterns,
  createRedactionPatterns,
  type CompiledSafetyPattern,
} from "./generatedPatterns";


function isLuhnValid(candidate: string): boolean {
  const digits = candidate.replace(/[ -]/g, "");
  if (!/^\d{13,19}$/.test(digits)) return false;

  let checksum = 0;
  const parity = digits.length % 2;
  for (let index = 0; index < digits.length; index += 1) {
    let value = Number(digits[index]);
    if (index % 2 === parity) {
      value *= 2;
      if (value > 9) value -= 9;
    }
    checksum += value;
  }
  return checksum % 10 === 0;
}


function isValidMatch(pattern: CompiledSafetyPattern["pattern"], value: string): boolean {
  return pattern.validator !== "luhn" || isLuhnValid(value);
}


function hasValidMatch({ pattern, regex }: CompiledSafetyPattern, text: string): boolean {
  let remaining = text;
  let match = regex.exec(remaining);
  while (match) {
    if (isValidMatch(pattern, match[0])) return true;
    const consumed = match.index + Math.max(match[0].length, 1);
    remaining = remaining.slice(consumed);
    match = regex.exec(remaining);
  }
  return false;
}


/**
 * Check if text contains any sensitive patterns.
 * 
 * Returns true if the text likely contains PII, API keys, tokens,
 * or other secrets that should not appear in public metadata.
 */
export function containsSensitivePattern(text: string): boolean {
  if (!text) return false;
  return createDetectionPatterns().some((pattern) => hasValidMatch(pattern, text));
}


export function detectSensitiveCategories(text: string): string[] {
  if (!text) return [];
  const categories = new Set<string>();
  for (const compiled of createDetectionPatterns()) {
    if (hasValidMatch(compiled, text)) categories.add(compiled.pattern.category);
  }
  return Array.from(categories).sort();
}


export function sanitizePublicText(text: string): string {
  let result = text;
  for (const { pattern, regex } of createRedactionPatterns()) {
    result = result.replace(
      regex,
      (match) => isValidMatch(pattern, match) ? pattern.replacement : match,
    );
  }
  return result;
}


/**
 * Create a safe, truncated preview of text for metadata.
 * 
 * 1. Checks for sensitive patterns — falls back to generic text
 * 2. Truncates to maxLength
 * 3. Cleans whitespace
 */
export function truncatePublicPreview(text: string, maxLength = 60): string {
  if (!text) return "Shared Arena Run";

  if (containsSensitivePattern(text)) {
    return "Shared Arena Run";
  }

  const clean = text.trim().replace(/\n/g, " ").replace(/\r/g, "").replace(/\s+/g, " ");

  if (clean.length <= maxLength) return clean;

  return clean.slice(0, maxLength - 3).trimEnd() + "...";
}


/**
 * Generate a safe page title for a debate/run.
 * 
 * For public runs with safe prompts: "Arena Run: {preview} | Consultaion"
 * For public runs with sensitive prompts: "Shared Arena Run | Consultaion"
 * For private runs: "Arena Run | Consultaion" (never expose prompt)
 */
export function safeMetadataTitle(prompt: string, isPublic = true): string {
  if (!isPublic) return "Arena Run | Consultaion";

  const preview = truncatePublicPreview(prompt, 57);
  if (preview === "Shared Arena Run") {
    return "Shared Arena Run | Consultaion";
  }

  return `Arena Run: ${preview} | Consultaion`;
}


/**
 * Generate a safe meta description for a debate/run.
 */
export function safeMetadataDescription(): string {
  return "Compare multiple AI model responses and read the synthesized answer.";
}
