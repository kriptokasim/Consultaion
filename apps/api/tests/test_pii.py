from safety.patterns import get_pattern
from safety.pii import ADDRESS_PATTERN, EMAIL_PATTERN, NAME_PATTERN, PHONE_PATTERN, scrub_text


def test_pii_scrubber_compiles_patterns_from_the_central_contract() -> None:
    assert EMAIL_PATTERN.pattern == get_pattern("email").source
    assert PHONE_PATTERN.pattern == get_pattern("phone").source
    assert NAME_PATTERN.pattern == get_pattern("name_heuristic").source
    assert ADDRESS_PATTERN.pattern == get_pattern("address_heuristic").source


def test_pii_scrubber_preserves_legacy_placeholders() -> None:
    text = "Please contact Jane Doe at jane@example.com or 555-123-4567."

    assert scrub_text(text, extended=True) == (
        "Please contact [redacted_name] at [redacted_email] or [redacted_phone]."
    )
