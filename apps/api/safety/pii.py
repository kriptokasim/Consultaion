"""
PII (Personally Identifiable Information) scrubbing utilities.

Provides functions to scrub sensitive information like emails and phone numbers
from text before sending to LLM providers.

Patchset 36.0: Added configurable extended patterns and metrics tracking.
"""

import logging
import os
from typing import Any

from safety.patterns import get_compiled_pattern, get_pattern

logger = logging.getLogger(__name__)

# Metrics tracking (in-memory for now, could be Redis)
_scrub_metrics = {
    "email_count": 0,
    "phone_count": 0,
    "name_count": 0,
    "address_count": 0,
}

EMAIL_PATTERN = get_compiled_pattern("email")
PHONE_PATTERN = get_compiled_pattern("phone")
NAME_PATTERN = get_compiled_pattern("name_heuristic")
ADDRESS_PATTERN = get_compiled_pattern("address_heuristic")


def _legacy_replacement(pattern_name: str) -> str:
    return get_pattern(pattern_name).replacement.lower()


def get_scrub_metrics() -> dict[str, int]:
    """
    Get current PII scrubbing metrics.
    
    Returns:
        Dictionary with counts of scrubbed items by type
    """
    return _scrub_metrics.copy()


def reset_scrub_metrics() -> None:
    """Reset all scrubbing metrics to zero."""
    global _scrub_metrics
    _scrub_metrics = {
        "email_count": 0,
        "phone_count": 0,
        "name_count": 0,
        "address_count": 0,
    }


def scrub_text(value: str, enable: bool = True, extended: bool | None = None) -> str:
    """
    Scrub PII from text content.
    
    Replaces email addresses and phone numbers with redaction placeholders.
    Optionally scrubs names and addresses if extended mode is enabled.
    
    Args:
        value: Text content to scrub
        enable: If False, returns original text unchanged (for disabling)
        extended: If True, also scrub names/addresses. If None, reads from PII_SCRUB_EXTENDED env var.
        
    Returns:
        Scrubbed text with PII replaced
        
    Examples:
        >>> scrub_text("Contact me at john@example.com")
        'Contact me at [redacted_email]'
        
        >>> scrub_text("Call 555-123-4567 for details")
        'Call [redacted_phone] for details'
        
        >>> scrub_text("John Smith lives at 123 Main Street", extended=True)
        '[redacted_name] lives at [redacted_address]'
    """
    if not enable:
        return value
    
    if extended is None:
        extended = os.getenv("PII_SCRUB_EXTENDED", "0") == "1"
    
    original_length = len(value)
    
    # Scrub emails
    email_matches = EMAIL_PATTERN.findall(value)
    email_count = len(email_matches)
    value = EMAIL_PATTERN.sub(_legacy_replacement("email"), value)
    _scrub_metrics["email_count"] += email_count
    
    # Scrub phone numbers
    phone_matches = PHONE_PATTERN.findall(value)
    phone_count = len(phone_matches)
    value = PHONE_PATTERN.sub(_legacy_replacement("phone"), value)
    _scrub_metrics["phone_count"] += phone_count
    
    # Extended scrubbing (names and addresses)
    name_count = 0
    address_count = 0
    if extended:
        # Scrub addresses first (more specific)
        address_matches = ADDRESS_PATTERN.findall(value)
        address_count = len(address_matches)
        value = ADDRESS_PATTERN.sub(_legacy_replacement("address_heuristic"), value)
        _scrub_metrics["address_count"] += address_count
        
        # Scrub names (after addresses to avoid false positives)
        name_matches = NAME_PATTERN.findall(value)
        name_count = len(name_matches)
        value = NAME_PATTERN.sub(_legacy_replacement("name_heuristic"), value)
        _scrub_metrics["name_count"] += name_count
    
    if email_count > 0 or phone_count > 0 or name_count > 0 or address_count > 0:
        logger.info(
            f"PII scrubbed: {email_count} emails, {phone_count} phones, "
            f"{name_count} names, {address_count} addresses "
            f"(original length: {original_length}, scrubbed length: {len(value)})"
        )
    
    return value


def scrub_messages(messages: list[dict[str, Any]], enable: bool = True, extended: bool | None = None) -> list[dict[str, Any]]:
    """
    Scrub PII from LLM message list.
    
    Processes a list of message dictionaries and scrubs the 'content' field
    of each message. Preserves all other message fields unchanged.
    
    Args:
        messages: List of message dictionaries (e.g., for LiteLLM)
        enable: If False, returns messages unchanged (for disabling)
        extended: If True, also scrub names/addresses. If None, reads from PII_SCRUB_EXTENDED env var.
        
    Returns:
        New list with scrubbed message content
        
    Example:
        >>> messages = [
        ...     {"role": "user", "content": "My email is test@example.com"},
        ...     {"role": "assistant", "content": "Got it!"}
        ... ]
        >>> scrubbed = scrub_messages(messages)
        >>> scrubbed[0]["content"]
        'My email is [redacted_email]'
    """
    if not enable:
        return messages
    
    scrubbed = []
    for msg in messages:
        new_msg = msg.copy()
        if "content" in new_msg and isinstance(new_msg["content"], str):
            new_msg["content"] = scrub_text(new_msg["content"], enable=True, extended=extended)
        scrubbed.append(new_msg)
    
    return scrubbed
