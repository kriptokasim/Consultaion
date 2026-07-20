from safety.patterns import detect_sensitive_categories
from utils.text_safety import contains_sensitive_pattern, sanitize_public_text


def test_valid_card_is_detected_and_redacted_only_after_luhn_validation() -> None:
    valid = "Use public Visa test number 4111 1111 1111 1111."
    invalid = "Order reference 4111 1111 1111 1112."

    assert contains_sensitive_pattern(valid)
    assert detect_sensitive_categories(valid) == ["payment_card"]
    assert sanitize_public_text(valid) == "Use public Visa test number [REDACTED_CC]."

    assert not contains_sensitive_pattern(invalid)
    assert detect_sensitive_categories(invalid) == []
    assert sanitize_public_text(invalid) == invalid


def test_backend_only_high_entropy_heuristic_is_not_silently_enabled() -> None:
    text = "A" * 48

    assert not contains_sensitive_pattern(text)
    assert detect_sensitive_categories(text) == []
    assert sanitize_public_text(text) == text
