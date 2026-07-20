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

from safety.patterns import (
    contains_sensitive_pattern as _contains_sensitive_pattern,
    redact_sensitive_patterns,
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
    return _contains_sensitive_pattern(text)


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

def sanitize_public_text(text: str) -> str:
    """
    Redact sensitive content from text for safe public display.

    Replaces API keys, tokens, PII, secrets with [REDACTED] placeholders.
    Used for metadata generation, public previews, analytics payloads.
    """
    return redact_sensitive_patterns(text)


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
