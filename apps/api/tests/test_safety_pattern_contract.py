from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from safety.patterns import detect_sensitive_categories
from utils.text_safety import contains_sensitive_pattern, sanitize_public_text

ROOT = Path(__file__).resolve().parents[3]
FIXTURES_PATH = ROOT / "config" / "safety-pattern-fixtures.json"


def test_backend_matches_shared_safety_fixtures() -> None:
    fixture_contract = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))

    assert fixture_contract["version"] == 1
    for fixture in fixture_contract["fixtures"]:
        text = fixture["input"]
        assert contains_sensitive_pattern(text) is fixture["expected_sensitive"], fixture["name"]
        assert detect_sensitive_categories(text) == fixture["expected_categories"], fixture["name"]
        sanitized = sanitize_public_text(text)
        for replacement in fixture["expected_redactions"]:
            assert replacement in sanitized, fixture["name"]
        if not fixture["expected_sensitive"]:
            assert sanitized == text, fixture["name"]


def test_generator_output_is_current_and_deterministic() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_web_patterns.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_shared_regexes_handle_long_input_with_bounded_runtime() -> None:
    text = ("ordinary prose with punctuation. " * 10_000).strip()

    started = time.monotonic()
    assert not contains_sensitive_pattern(text)
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
