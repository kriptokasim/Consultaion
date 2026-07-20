from __future__ import annotations

import re

import pytest
from safety.patterns import (
    SafetyPatternContractError,
    get_pattern,
    is_luhn_valid,
    load_pattern_contract,
)


def test_shared_patterns_compile_and_detection_regexes_are_portable() -> None:
    contract = load_pattern_contract()

    assert contract.version == 1
    assert len({pattern.name for pattern in contract.patterns}) == len(contract.patterns)
    for pattern in contract.patterns:
        re.compile(pattern.source, re.IGNORECASE if pattern.case_insensitive else 0)
        if pattern.platform == "shared":
            assert "(?P<" not in pattern.source
            assert "(?P=" not in pattern.source
            assert "\\A" not in pattern.source
            assert "\\Z" not in pattern.source


def test_email_pattern_does_not_treat_pipe_as_a_letter() -> None:
    email = get_pattern("email")

    assert "[A-Za-z]" in email.source
    assert "[A-Z|a-z]" not in email.source


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("4111 1111 1111 1111", True),
        ("5555-5555-5555-4444", True),
        ("4111111111111112", False),
        ("1234567890123", False),
        ("555-123-4567", False),
        ("411111111111", False),
        ("41111111111111111111", False),
    ],
)
def test_luhn_requires_13_to_19_digits(candidate: str, expected: bool) -> None:
    assert is_luhn_valid(candidate) is expected


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data["patterns"].append(dict(data["patterns"][0])),
        lambda data: data["patterns"][0].update(source="("),
        lambda data: data["patterns"][0].update(replacement=""),
        lambda data: data["patterns"][0].update(unsupported_flag=True),
        lambda data: data["patterns"][0].update(source=r"(?P<token>abc)"),
    ],
)
def test_contract_rejects_invalid_definitions(tmp_path, mutate) -> None:
    import json

    source = load_pattern_contract().to_dict()
    mutate(source)
    path = tmp_path / "patterns.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(SafetyPatternContractError):
        load_pattern_contract(path)
