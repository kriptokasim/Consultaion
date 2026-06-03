"""
Sensitive text detection and redaction for public metadata, previews, and analytics.

Builds on the existing PII scrubber (safety.pii) and adds patterns for:
- API keys (OpenAI, Anthropic, Google, etc.)
- JWT tokens and bearer tokens
- Credit card numbers
- High-entropy secrets and passwords
- URLs with embedded tokens

This module is used for:
1. OG metadata title/description generation
2. Public run previews
3. Analytics event payloads (to prevent prompt leakage)
4. Audit log sanitization
"""

from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Sensitive patterns
# ---------------------------------------------------------------------------

# API Key patterns — provider-specific prefixes
_API_KEY_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.ASCII),          # OpenAI
    re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}", re.ASCII),    # Anthropic
    re.compile(r"sk-proj-[a-zA-Z0-9\-]{20,}", re.ASCII),   # OpenAI project keys
    re.compile(r"AIza[a-zA-Z0-9\-_]{30,}", re.ASCII),      # Google API
    re.compile(r"gsk_[a-zA-Z0-9]{20,}", re.ASCII),         # Groq
    re.compile(r"xai-[a-zA-Z0-9]{20,}", re.ASCII),         # xAI
]

# Generic high-entropy token (long alphanumeric strings — likely tokens/keys)
_HIGH_ENTROPY_TOKEN = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")

# JWT-like pattern (three dot-separated base64 segments)
_JWT_PATTERN = re.compile(
    r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
)

# Bearer token in text
_BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+", re.IGNORECASE)

# Credit card-like numbers (13-19 digits, with optional separators)
_CREDIT_CARD_PATTERN = re.compile(
    r"\b(?:\d{4}[-\s]?){3,4}\d{1,4}\b"
)

# Explicit secret assignments (e.g., PASSWORD=..., API_KEY=..., SECRET=...)
_SECRET_ASSIGNMENT = re.compile(
    r"(?:PASSWORD|SECRET|API_KEY|APIKEY|ACCESS_TOKEN|AUTH_TOKEN|PRIVATE_KEY|"
    r"SECRET_KEY|ENCRYPTION_KEY)\s*[=:]\s*\S+",
    re.IGNORECASE,
)

# URLs with token/key query params
_URL_WITH_TOKEN = re.compile(
    r"https?://[^\s]+[?&](?:token|key|secret|api_key|access_token|auth)=[^\s&]+",
    re.IGNORECASE,
)

# Email pattern (reuse from safety.pii)
_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    re.IGNORECASE,
)

# Phone pattern (simplified)
_PHONE_PATTERN = re.compile(
    r"(\+\d{1,3}[-.\s]?)?(\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}"
)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def contains_sensitive_pattern(text: str) -> bool:
    """
    Check if text contains any sensitive patterns.

    Returns True if the text likely contains PII, API keys, tokens,
    or other secrets that should not appear in public metadata.
    """
    if not text:
        return False

    # Check each pattern category
    for pattern in _API_KEY_PATTERNS:
        if pattern.search(text):
            return True

    if _JWT_PATTERN.search(text):
        return True

    if _BEARER_PATTERN.search(text):
        return True

    if _SECRET_ASSIGNMENT.search(text):
        return True

    if _URL_WITH_TOKEN.search(text):
        return True

    if _EMAIL_PATTERN.search(text):
        return True

    if _PHONE_PATTERN.search(text):
        return True

    if _CREDIT_CARD_PATTERN.search(text):
        return True

    return False


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

def sanitize_public_text(text: str) -> str:
    """
    Redact sensitive content from text for safe public display.

    Replaces API keys, tokens, PII, secrets with [REDACTED] placeholders.
    Used for metadata generation, public previews, analytics payloads.
    """
    if not text:
        return text

    result = text

    # Redact API keys
    for pattern in _API_KEY_PATTERNS:
        result = pattern.sub("[REDACTED_API_KEY]", result)

    # Redact JWTs
    result = _JWT_PATTERN.sub("[REDACTED_TOKEN]", result)

    # Redact Bearer tokens
    result = _BEARER_PATTERN.sub("[REDACTED_TOKEN]", result)

    # Redact secret assignments
    result = _SECRET_ASSIGNMENT.sub("[REDACTED_SECRET]", result)

    # Redact URLs with tokens
    result = _URL_WITH_TOKEN.sub("[REDACTED_URL]", result)

    # Redact emails
    result = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", result)

    # Redact phone numbers
    result = _PHONE_PATTERN.sub("[REDACTED_PHONE]", result)

    # Redact credit card numbers
    result = _CREDIT_CARD_PATTERN.sub("[REDACTED_CC]", result)

    return result


def truncate_public_preview(text: str, max_length: int = 60) -> str:
    """
    Create a safe, truncated preview of text for metadata.

    1. Sanitizes sensitive content
    2. Truncates to max_length
    3. Falls back to generic text if content appears sensitive

    Returns a safe string for use in OG titles, descriptions, etc.
    """
    if not text:
        return "Shared Arena Run"

    # Check if the original text contains sensitive patterns
    if contains_sensitive_pattern(text):
        return "Shared Arena Run"

    # Clean and truncate
    clean = text.strip().replace("\n", " ").replace("\r", "")
    # Collapse multiple spaces
    clean = re.sub(r"\s+", " ", clean)

    if len(clean) <= max_length:
        return clean

    return clean[:max_length - 3].rstrip() + "..."


def safe_metadata_title(prompt: str, is_public: bool = True) -> str:
    """
    Generate a safe page title for a debate/run.

    For public runs with safe prompts: "Arena Run: {preview} | Consultaion"
    For public runs with sensitive prompts: "Shared Arena Run | Consultaion"
    For private runs: "Arena Run | Consultaion" (never expose prompt)
    """
    if not is_public:
        return "Arena Run | Consultaion"

    preview = truncate_public_preview(prompt, max_length=57)
    if preview == "Shared Arena Run":
        return "Shared Arena Run | Consultaion"

    return f"Arena Run: {preview} | Consultaion"


def safe_metadata_description(prompt: str, is_public: bool = True) -> str:
    """
    Generate a safe meta description for a debate/run.

    For public runs with safe prompts: uses a preview + generic suffix.
    For sensitive/private runs: uses a fully generic description.
    """
    generic = "Compare multiple AI model responses and read the synthesized answer."

    if not is_public:
        return generic

    if contains_sensitive_pattern(prompt):
        return generic

    return generic
