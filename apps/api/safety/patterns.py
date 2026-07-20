"""Validated sensitive-pattern contract shared by backend and frontend."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONTRACT_PATH = ROOT / "config" / "safety-patterns.json"

_PATTERN_KEYS = {
    "name",
    "category",
    "source",
    "case_insensitive",
    "global_for_redaction",
    "enabled_in_detection",
    "enabled_in_redaction",
    "replacement",
    "platform",
    "consumers",
    "validator",
}
_REQUIRED_PATTERN_KEYS = _PATTERN_KEYS - {"validator"}
_PLATFORMS = {"shared", "backend"}
_CONSUMERS = {"text_safety", "pii"}
_VALIDATORS = {None, "luhn"}
_PYTHON_ONLY_SHARED_SYNTAX = ("(?P<", "(?P=", "\\A", "\\Z", "\\G")


class SafetyPatternContractError(ValueError):
    """Raised when the declarative safety contract is invalid."""


@dataclass(frozen=True)
class SafetyPattern:
    name: str
    category: str
    source: str
    case_insensitive: bool
    global_for_redaction: bool
    enabled_in_detection: bool
    enabled_in_redaction: bool
    replacement: str
    platform: str
    consumers: tuple[str, ...]
    validator: str | None = None

    @property
    def flags(self) -> int:
        return re.IGNORECASE if self.case_insensitive else 0

    def compile(self) -> re.Pattern[str]:
        return re.compile(self.source, self.flags)


@dataclass(frozen=True)
class SafetyPatternContract:
    version: int
    patterns: tuple[SafetyPattern, ...]

    def to_dict(self) -> dict[str, Any]:
        patterns: list[dict[str, Any]] = []
        for pattern in self.patterns:
            serialized = asdict(pattern)
            serialized["consumers"] = list(pattern.consumers)
            if pattern.validator is None:
                serialized.pop("validator")
            patterns.append(serialized)
        return {"version": self.version, "patterns": patterns}


def _require_bool(raw: dict[str, Any], key: str, name: str) -> bool:
    value = raw[key]
    if not isinstance(value, bool):
        raise SafetyPatternContractError(f"Pattern {name!r} field {key!r} must be boolean")
    return value


def _parse_pattern(raw: Any, index: int) -> SafetyPattern:
    if not isinstance(raw, dict):
        raise SafetyPatternContractError(f"Pattern at index {index} must be an object")

    keys = set(raw)
    missing = _REQUIRED_PATTERN_KEYS - keys
    unknown = keys - _PATTERN_KEYS
    if missing:
        raise SafetyPatternContractError(f"Pattern at index {index} is missing: {sorted(missing)}")
    if unknown:
        raise SafetyPatternContractError(f"Pattern at index {index} has unsupported fields: {sorted(unknown)}")

    name = raw["name"]
    category = raw["category"]
    source = raw["source"]
    replacement = raw["replacement"]
    platform = raw["platform"]
    consumers = raw["consumers"]
    validator = raw.get("validator")

    if not isinstance(name, str) or not name:
        raise SafetyPatternContractError(f"Pattern at index {index} has an invalid name")
    if not isinstance(category, str) or not category:
        raise SafetyPatternContractError(f"Pattern {name!r} has an invalid category")
    if not isinstance(source, str) or not source:
        raise SafetyPatternContractError(f"Pattern {name!r} has an invalid source")
    if not isinstance(replacement, str):
        raise SafetyPatternContractError(f"Pattern {name!r} has an invalid replacement")
    if platform not in _PLATFORMS:
        raise SafetyPatternContractError(f"Pattern {name!r} has unsupported platform {platform!r}")
    if not isinstance(consumers, list) or not consumers or any(item not in _CONSUMERS for item in consumers):
        raise SafetyPatternContractError(f"Pattern {name!r} has unsupported consumers")
    if len(set(consumers)) != len(consumers):
        raise SafetyPatternContractError(f"Pattern {name!r} repeats a consumer")
    if validator not in _VALIDATORS:
        raise SafetyPatternContractError(f"Pattern {name!r} has unsupported validator {validator!r}")

    enabled_in_redaction = _require_bool(raw, "enabled_in_redaction", name)
    if enabled_in_redaction and not replacement:
        raise SafetyPatternContractError(f"Pattern {name!r} needs a redaction replacement")
    if platform == "shared" and any(token in source for token in _PYTHON_ONLY_SHARED_SYNTAX):
        raise SafetyPatternContractError(f"Pattern {name!r} uses Python-only regex syntax")

    case_insensitive = _require_bool(raw, "case_insensitive", name)
    try:
        re.compile(source, re.IGNORECASE if case_insensitive else 0)
    except re.error as exc:
        raise SafetyPatternContractError(f"Pattern {name!r} has invalid regex: {exc}") from exc

    return SafetyPattern(
        name=name,
        category=category,
        source=source,
        case_insensitive=case_insensitive,
        global_for_redaction=_require_bool(raw, "global_for_redaction", name),
        enabled_in_detection=_require_bool(raw, "enabled_in_detection", name),
        enabled_in_redaction=enabled_in_redaction,
        replacement=replacement,
        platform=platform,
        consumers=tuple(consumers),
        validator=validator,
    )


@lru_cache(maxsize=None)
def load_pattern_contract(path: str | Path = DEFAULT_CONTRACT_PATH) -> SafetyPatternContract:
    contract_path = Path(path)
    try:
        raw = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyPatternContractError(f"Unable to load safety contract {contract_path}: {exc}") from exc

    if not isinstance(raw, dict) or set(raw) != {"version", "patterns"}:
        raise SafetyPatternContractError("Safety contract must contain only version and patterns")
    if raw["version"] != 1:
        raise SafetyPatternContractError(f"Unsupported safety contract version: {raw['version']!r}")
    if not isinstance(raw["patterns"], list) or not raw["patterns"]:
        raise SafetyPatternContractError("Safety contract patterns must be a non-empty list")

    patterns = tuple(_parse_pattern(item, index) for index, item in enumerate(raw["patterns"]))
    names = [pattern.name for pattern in patterns]
    if len(names) != len(set(names)):
        raise SafetyPatternContractError("Safety contract pattern names must be unique")

    return SafetyPatternContract(version=raw["version"], patterns=patterns)


def get_pattern(name: str) -> SafetyPattern:
    for pattern in load_pattern_contract().patterns:
        if pattern.name == name:
            return pattern
    raise KeyError(f"Unknown safety pattern: {name}")


def get_compiled_pattern(name: str) -> re.Pattern[str]:
    return get_pattern(name).compile()


def is_luhn_valid(candidate: str) -> bool:
    digits = "".join(character for character in candidate if character.isdigit())
    if not 13 <= len(digits) <= 19 or any(character not in "0123456789" for character in digits):
        return False

    checksum = 0
    parity = len(digits) % 2
    for index, character in enumerate(digits):
        value = int(character)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        checksum += value
    return checksum % 10 == 0


def _is_valid_match(pattern: SafetyPattern, value: str) -> bool:
    return pattern.validator != "luhn" or is_luhn_valid(value)


def _iter_valid_matches(pattern: SafetyPattern, text: str) -> Iterator[re.Match[str]]:
    for match in pattern.compile().finditer(text):
        if _is_valid_match(pattern, match.group(0)):
            yield match


def iter_patterns(*, consumer: str, platform: str | None = None) -> Iterator[SafetyPattern]:
    if consumer not in _CONSUMERS:
        raise ValueError(f"Unknown safety pattern consumer: {consumer}")
    for pattern in load_pattern_contract().patterns:
        if consumer not in pattern.consumers:
            continue
        if platform is not None and pattern.platform != platform:
            continue
        yield pattern


def detect_sensitive_categories(text: str, *, consumer: str = "text_safety") -> list[str]:
    if not text:
        return []
    categories = {
        pattern.category
        for pattern in iter_patterns(consumer=consumer)
        if pattern.enabled_in_detection and next(_iter_valid_matches(pattern, text), None) is not None
    }
    return sorted(categories)


def contains_sensitive_pattern(text: str, *, consumer: str = "text_safety") -> bool:
    if not text:
        return False
    return any(
        next(_iter_valid_matches(pattern, text), None) is not None
        for pattern in iter_patterns(consumer=consumer)
        if pattern.enabled_in_detection
    )


def redact_sensitive_patterns(text: str, *, consumer: str = "text_safety") -> str:
    result = text
    for pattern in iter_patterns(consumer=consumer):
        if not pattern.enabled_in_redaction:
            continue
        compiled = pattern.compile()
        if pattern.validator:
            result = compiled.sub(
                lambda match, active_pattern=pattern: (
                    active_pattern.replacement
                    if _is_valid_match(active_pattern, match.group(0))
                    else match.group(0)
                ),
                result,
            )
        else:
            result = compiled.sub(pattern.replacement, result)
    return result
