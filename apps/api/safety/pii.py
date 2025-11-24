"""
PII (Personally Identifiable Information) scrubbing utilities.

Provides functions to scrub sensitive information like emails and phone numbers
from text before sending to LLM providers.

Patchset 29.0
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Email pattern: matches most common email formats
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    re.IGNORECASE
)

# Phone patterns: matches various phone number formats
# International: +1-234-567-8900, +1 234 567 8900, +12345678900
# US domestic: (234) 567-8900, 234-567-8900, 234.567.8900, 2345678900
PHONE_PATTERN = re.compile(
    r'(\+\d{1,3}[-.\s]?)?'  # Optional country code
    r'(\(\d{3}\)|\d{3})[-.\s]?'  # Area code
    r'\d{3}[-.\s]?'  # First 3 digits
    r'\d{4}'  # Last 4 digits
)


def scrub_text(value: str, enable: bool = True) -> str:
    """
    Scrub PII from text content.
    
    Replaces email addresses and phone numbers with redaction placeholders.
    
    Args:
        value: Text content to scrub
        enable: If False, returns original text unchanged (for disabling)
        
    Returns:
        Scrubbed text with PII replaced
        
    Examples:
        >>> scrub_text("Contact me at john@example.com")
        'Contact me at [redacted_email]'
        
        >>> scrub_text("Call 555-123-4567 for details")
        'Call [redacted_phone] for details'
    """
    if not enable:
        return value
    
    original_length = len(value)
    
    # Scrub emails
    email_count = len(EMAIL_PATTERN.findall(value))
    value = EMAIL_PATTERN.sub('[redacted_email]', value)
    
    # Scrub phone numbers
    phone_count = len(PHONE_PATTERN.findall(value))
    value = PHONE_PATTERN.sub('[redacted_phone]', value)
    
    if email_count > 0 or phone_count > 0:
        logger.info(
            f"PII scrubbed: {email_count} emails, {phone_count} phones "
            f"(original length: {original_length}, scrubbed length: {len(value)})"
        )
    
    return value


def scrub_messages(messages: list[dict[str, Any]], enable: bool = True) -> list[dict[str, Any]]:
    """
    Scrub PII from LLM message list.
    
    Processes a list of message dictionaries and scrubs the 'content' field
    of each message. Preserves all other message fields unchanged.
    
    Args:
        messages: List of message dictionaries (e.g., for LiteLLM)
        enable: If False, returns messages unchanged (for disabling)
        
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
            new_msg["content"] = scrub_text(new_msg["content"], enable=True)
        scrubbed.append(new_msg)
    
    return scrubbed
