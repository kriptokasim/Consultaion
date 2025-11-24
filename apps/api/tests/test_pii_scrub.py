"""
Tests for PII scrubbing functionality.

Patchset 29.0
"""

import pytest

from safety.pii import scrub_text, scrub_messages


def test_scrub_email():
    """Email addresses should be redacted."""
    text = "Contact me at john.doe@example.com for more info"
    scrubbed = scrub_text(text)
    
    assert "[redacted_email]" in scrubbed
    assert "john.doe@example.com" not in scrubbed


def test_scrub_multiple_emails():
    """Multiple email addresses should be redacted."""
    text = "Email alice@test.com or bob@company.org"
    scrubbed = scrub_text(text)
    
    assert scrubbed.count("[redacted_email]") == 2
    assert "alice@test.com" not in scrubbed
    assert "bob@company.org" not in scrubbed


def test_scrub_phone_us_format():
    """US phone numbers should be redacted."""
    text = "Call me at 555-123-4567"
    scrubbed = scrub_text(text)
    
    assert "[redacted_phone]" in scrubbed
    assert "555-123-4567" not in scrubbed


def test_scrub_phone_parentheses():
    """Phone with parentheses should be redacted."""
    text = "My number is (555) 123-4567"
    scrubbed = scrub_text(text)
    
    assert "[redacted_phone]" in scrubbed


def test_scrub_phone_international():
    """International phone format should be redacted."""
    text = "International: +1-555-123-4567"
    scrubbed = scrub_text(text)
    
    assert "[redacted_phone]" in scrubbed


def test_scrub_text_disabled():
    """Scrubbing should be bypassed when disabled."""
    text = "Email: test@example.com Phone: 555-123-4567"
    scrubbed = scrub_text(text, enable=False)
    
    assert scrubbed == text
    assert "test@example.com" in scrubbed


def test_scrub_plain_text_unchanged():
    """Plain text without PII should remain unchanged."""
    text = "This is a normal sentence without any PII."
    scrubbed = scrub_text(text)
    
    assert scrubbed == text


def test_scrub_messages_user_content():
    """Messages should have content scrubbed."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "My email is user@example.com"},
        {"role": "assistant", "content": "I understand"},
    ]
    
    scrubbed = scrub_messages(messages)
    
    assert "[redacted_email]" in scrubbed[1]["content"]
    assert "user@example.com" not in scrubbed[1]["content"]
    # System and assistant messages should be unchanged
    assert scrubbed[0]["content"] == messages[0]["content"]
    assert scrubbed[2]["content"] == messages[2]["content"]


def test_scrub_messages_disabled():
    """Message scrubbing should be byp

assed when disabled."""
    messages = [
        {"role": "user", "content": "Email: test@example.com"}
    ]
    
    scrubbed = scrub_messages(messages, enable=False)
    
    assert scrubbed[0]["content"] == messages[0]["content"]


def test_scrub_messages_preserves_structure():
    """Message structure should be preserved."""
    messages = [
        {"role": "user", "content": "Test", "extra": "data"}
    ]
    
    scrubbed = scrub_messages(messages)
    
    assert scrubbed[0]["role"] == "user"
    assert scrubbed[0]["extra"] == "data"


def test_scrub_email_various_formats():
    """Various email formats should be scrubbed."""
    test_cases = [
        "simple@example.com",
        "name.surname@example.co.uk",
        "test+tag@example.com",
        "user_123@test-domain.org",
    ]
    
    for email in test_cases:
        text = f"Contact: {email}"
        scrubbed = scrub_text(text)
        assert "[redacted_email]" in scrubbed
        assert email not in scrubbed
