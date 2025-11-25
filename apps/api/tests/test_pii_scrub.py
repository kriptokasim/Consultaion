"""
Tests for PII scrubbing functionality.

Patchset 36.0: Added tests for extended patterns and metrics.
"""


from safety.pii import get_scrub_metrics, reset_scrub_metrics, scrub_messages, scrub_text


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
    """Message scrubbing should be bypassed when disabled."""
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


# Patchset 36.0: Extended pattern tests

def test_scrub_name_extended():
    """Names should be redacted when extended mode is enabled."""
    text = "John Smith is a great developer"
    scrubbed = scrub_text(text, extended=True)
    
    assert "[redacted_name]" in scrubbed
    assert "John Smith" not in scrubbed


def test_scrub_name_not_extended():
    """Names should NOT be redacted when extended mode is disabled."""
    text = "John Smith is a great developer"
    scrubbed = scrub_text(text, extended=False)
    
    assert "[redacted_name]" not in scrubbed
    assert "John Smith" in scrubbed


def test_scrub_address_extended():
    """Addresses should be redacted when extended mode is enabled."""
    text = "I live at 123 Main Street in the city"
    scrubbed = scrub_text(text, extended=True)
    
    assert "[redacted_address]" in scrubbed
    assert "123 Main Street" not in scrubbed


def test_scrub_address_not_extended():
    """Addresses should NOT be redacted when extended mode is disabled."""
    text = "I live at 123 Main Street in the city"
    scrubbed = scrub_text(text, extended=False)
    
    assert "[redacted_address]" not in scrubbed
    assert "123 Main Street" in scrubbed


def test_scrub_extended_env_var(monkeypatch):
    """Extended scrubbing should respect PII_SCRUB_EXTENDED env var."""
    monkeypatch.setenv("PII_SCRUB_EXTENDED", "1")
    
    text = "John Doe lives at 456 Oak Avenue"
    scrubbed = scrub_text(text)  # extended=None should read from env
    
    assert "[redacted_name]" in scrubbed
    assert "[redacted_address]" in scrubbed


def test_scrub_metrics_tracking():
    """Metrics should track scrubbed items."""
    reset_scrub_metrics()
    
    scrub_text("Email: test@example.com")
    scrub_text("Phone: 555-123-4567")
    scrub_text("Contact John Smith at 789 Pine Road", extended=True)
    
    metrics = get_scrub_metrics()
    assert metrics["email_count"] >= 1
    assert metrics["phone_count"] >= 1
    assert metrics["name_count"] >= 1
    assert metrics["address_count"] >= 1


def test_scrub_metrics_reset():
    """Metrics should be resettable."""
    scrub_text("test@example.com")
    reset_scrub_metrics()
    
    metrics = get_scrub_metrics()
    assert metrics["email_count"] == 0
    assert metrics["phone_count"] == 0
    assert metrics["name_count"] == 0
    assert metrics["address_count"] == 0


def test_scrub_messages_extended():
    """Messages should support extended scrubbing."""
    messages = [
        {"role": "user", "content": "I'm Jane Doe from 100 Elm Street"}
    ]
    
    scrubbed = scrub_messages(messages, extended=True)
    
    assert "[redacted_name]" in scrubbed[0]["content"]
    assert "[redacted_address]" in scrubbed[0]["content"]
