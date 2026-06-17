import pytest
from utils.redact import redact_pii, RedactOptions

def test_redact_pii_no_options():
    text = "My email is test@example.com and phone is 555-1234."
    redacted = redact_pii(text)
    assert "test@example.com" not in redacted
    assert "555-1234" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_PHONE]" in redacted

def test_redact_pii_with_options():
    text = "My email is test@example.com and phone is 555-1234."
    opts = RedactOptions(redact_email=False, redact_phone=True)
    redacted = redact_pii(text, options=opts)
    assert "test@example.com" in redacted
    assert "555-1234" not in redacted
    assert "[REDACTED_PHONE]" in redacted

def test_redact_pii_empty():
    assert redact_pii("") == ""
    assert redact_pii(None) is None
