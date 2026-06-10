"""Claim quality filter — cleans and validates semantic claims.

Removes noisy pseudo-claims such as intro phrases, markdown artifacts,
section headers, and fragments that are not decision-relevant propositions.
"""

from __future__ import annotations

import re
from typing import List

# Intro/transition phrases that indicate filler, not a real claim
_INTRO_BLOCKLIST = [
    "here's a structured",
    "here's a step-by-step",
    "here is a structured",
    "here is a step-by-step",
    "must-include slides",
    "let me walk you through",
    "let me outline",
    "in this guide",
    "in this section",
    "below is a",
    "below are the",
    "the following is",
    "the following are",
    "key takeaways include",
    "key points to consider",
    "here are some",
    "here are the",
    "consider the following",
    "this document outlines",
    "this guide covers",
    "here's a comprehensive",
    "here’s a comprehensive",
    "here's a concise",
    "here’s a concise",
    "here's a draft",
    "here’s a draft",
    "here's a framework",
    "here’s a framework",
    "designed to accelerate",
    "this report synthesizes",
    "this policy framework",
]

_INTRO_REGEXES = [
    re.compile(r"^here[’']s\s+(a\s+)?(comprehensive|concise|structured|step-by-step|draft|framework)", re.I),
    re.compile(r"^this\s+(report|document|policy)\s+(synthesizes|outlines|provides)", re.I),
]

# Markdown artifact patterns to strip
_MARKDOWN_PATTERNS = [
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),           # **bold**
    (re.compile(r"\*(.+?)\*"), r"\1"),                # *italic*
    (re.compile(r"__(.+?)__"), r"\1"),                # __bold__
    (re.compile(r"_(.+?)_"), r"\1"),                  # _italic_
    (re.compile(r"^#{1,6}\s*", re.MULTILINE), ""),    # ## headings
    (re.compile(r"^[-*+]\s+", re.MULTILINE), ""),     # - bullet points
    (re.compile(r"^\d+[.)]\s+", re.MULTILINE), ""),   # 1. numbered lists
    (re.compile(r"`(.+?)`"), r"\1"),                  # `code`
    (re.compile(r"```.*?```", re.DOTALL), ""),         # ```code blocks```
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),    # [link text](url)
]

# Words that don't count as "meaningful" for length checking
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "and", "or",
    "but", "if", "then", "so", "it", "its", "this", "that", "these",
    "those", "not", "no", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "than", "too", "very",
}


def clean_claim_text(claim: str) -> str:
    """Strip markdown artifacts, leading bullets/numbers, and extra whitespace.

    Returns a clean, plain-text version of the claim.
    """
    text = claim.strip()

    # Apply markdown stripping patterns
    for pattern, replacement in _MARKDOWN_PATTERNS:
        text = pattern.sub(replacement, text)

    # Remove residual multiple spaces
    text = re.sub(r"\s+", " ", text).strip()

    # Remove trailing/leading punctuation artifacts
    text = text.strip("-*•·–—")
    text = text.strip()

    return text


def _count_meaningful_words(text: str) -> int:
    """Count words that are not stopwords."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return sum(1 for w in words if w not in _STOPWORDS)


def _looks_like_heading(text: str) -> bool:
    """Detect if the text looks like a section heading rather than a proposition.

    Headings tend to be short, lack verbs, and use title case or all caps.
    """
    # Very short texts that are title-case or all-caps are likely headings
    words = text.split()
    if len(words) <= 4:
        # Check if it's title-case (most words capitalized)
        capitalized = sum(1 for w in words if w[0].isupper() or w.isupper())
        if capitalized >= len(words) * 0.75:
            return True

    # Ends with a colon → likely a heading
    if text.rstrip().endswith(":"):
        return True

    return False


def is_valid_semantic_claim(claim: str) -> bool:
    """Validate whether a claim is a real, decision-relevant semantic proposition.

    Returns False for:
    - Intro/transition phrases
    - Section headers without propositions
    - Markdown artifacts that are just formatting
    - Fragments shorter than 6 meaningful words
    - Generic filler text
    - Duplicate title-like claims
    """
    if not claim or not claim.strip():
        return False

    cleaned = clean_claim_text(claim)

    if not cleaned:
        return False

    lower = cleaned.lower().strip()

    # Check against intro blocklist
    for phrase in _INTRO_BLOCKLIST:
        if lower.startswith(phrase):
            return False

    # Check against intro regex patterns
    for regex in _INTRO_REGEXES:
        if regex.match(cleaned):
            return False

    # Check for fragments that are too short
    if _count_meaningful_words(cleaned) < 6:
        return False

    # Check if it looks like a heading, not a proposition
    if _looks_like_heading(cleaned):
        return False

    # Check for claims that are just ellipsis or placeholder
    if cleaned in ("...", "…", "etc.", "etc", "TBD", "N/A"):
        return False

    return True


def filter_claims(claims: List[str]) -> List[str]:
    """Clean and filter a list of claims, returning only valid semantic propositions."""
    result = []
    seen_normalized = set()

    for claim in claims:
        cleaned = clean_claim_text(claim)
        if not is_valid_semantic_claim(cleaned):
            continue

        # Deduplicate by normalized lowercase
        normalized = cleaned.lower().strip()
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)

        result.append(cleaned)

    return result
