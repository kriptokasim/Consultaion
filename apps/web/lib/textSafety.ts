/**
 * Sensitive text detection and redaction for public metadata, previews, and analytics.
 * 
 * Frontend equivalent of the backend utils/text_safety.py module.
 * Used for:
 * - OG metadata generation in Next.js generateMetadata
 * - Public run title previews
 * - Analytics event payloads (prevent prompt leakage)
 */

// ---------------------------------------------------------------------------
// Sensitive pattern detection
// ---------------------------------------------------------------------------

/** OpenAI, Anthropic, Google, Groq, xAI API key patterns */
const API_KEY_PATTERNS = [
  /sk-[a-zA-Z0-9]{20,}/g,
  /sk-ant-[a-zA-Z0-9\-]{20,}/g,
  /sk-proj-[a-zA-Z0-9\-]{20,}/g,
  /AIza[a-zA-Z0-9\-_]{30,}/g,
  /gsk_[a-zA-Z0-9]{20,}/g,
  /xai-[a-zA-Z0-9]{20,}/g,
];

/** JWT-like tokens (three dot-separated base64 segments) */
const JWT_PATTERN = /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g;

/** Bearer tokens in text */
const BEARER_PATTERN = /Bearer\s+[A-Za-z0-9\-._~+/]+/gi;

/** Credit card-like numbers (13-19 digits) */
const CREDIT_CARD_PATTERN = /\b(?:\d{4}[-\s]?){3,4}\d{1,4}\b/g;

/** Explicit secret assignments (PASSWORD=..., API_KEY=..., etc.) */
const SECRET_ASSIGNMENT = /(?:PASSWORD|SECRET|API_KEY|APIKEY|ACCESS_TOKEN|AUTH_TOKEN|PRIVATE_KEY|SECRET_KEY|ENCRYPTION_KEY)\s*[=:]\s*\S+/gi;

/** URLs with token/key query params */
const URL_WITH_TOKEN = /https?:\/\/[^\s]+[?&](?:token|key|secret|api_key|access_token|auth)=[^\s&]+/gi;

/** Email addresses */
const EMAIL_PATTERN = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/gi;

/** Phone numbers (US + international) */
const PHONE_PATTERN = /(\+\d{1,3}[-.\s]?)?(\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}/g;


/**
 * Check if text contains any sensitive patterns.
 * 
 * Returns true if the text likely contains PII, API keys, tokens,
 * or other secrets that should not appear in public metadata.
 */
export function containsSensitivePattern(text: string): boolean {
  if (!text) return false;

  for (const pattern of API_KEY_PATTERNS) {
    pattern.lastIndex = 0;
    if (pattern.test(text)) return true;
  }

  JWT_PATTERN.lastIndex = 0;
  if (JWT_PATTERN.test(text)) return true;

  BEARER_PATTERN.lastIndex = 0;
  if (BEARER_PATTERN.test(text)) return true;

  SECRET_ASSIGNMENT.lastIndex = 0;
  if (SECRET_ASSIGNMENT.test(text)) return true;

  URL_WITH_TOKEN.lastIndex = 0;
  if (URL_WITH_TOKEN.test(text)) return true;

  EMAIL_PATTERN.lastIndex = 0;
  if (EMAIL_PATTERN.test(text)) return true;

  PHONE_PATTERN.lastIndex = 0;
  if (PHONE_PATTERN.test(text)) return true;

  CREDIT_CARD_PATTERN.lastIndex = 0;
  if (CREDIT_CARD_PATTERN.test(text)) return true;

  return false;
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
