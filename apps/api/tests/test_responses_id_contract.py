"""Ids on the /responses contract must be strings.

Message.id is an autoincrement integer primary key, but the wire contract in
apps/web/lib/api/arenaSchemas.ts declares `id: z.string()`, consistent with
debate_id and response_id. Emitting the raw int made Zod reject the whole
payload -- "items.0.id: Expected string, received number" -- so the workspace's
/responses fetch failed outright, responses never rendered, and divergence could
not be extracted. Observed live, repeatedly, during a real run.

Coercion belongs on the server: ids are identifiers rather than numbers, and a
JSON integer id is a precision hazard in JS regardless of this schema.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


def _serialize(msg_id, response_id=None):
    """Build a Message-shaped stand-in and run it through the row serializer.

    SimpleNamespace rather than a class body: a class body does not close over
    the enclosing function's parameters, so `response_id = response_id` there
    raises NameError instead of doing the obvious thing.
    """
    from types import SimpleNamespace

    from services import debate_responses as mod

    msg = SimpleNamespace(
        id=msg_id,
        debate_id="deb-1",
        round_index=0,
        role="arena_response",
        response_id=response_id,
        created_at=None,
        content="hello",
        persona="Model A",
        meta_json=None,
    )
    return mod._normalize_message(msg, is_public=False)


def test_frontend_schema_still_demands_string_ids():
    """Pin the other half of the contract, so a schema change is noticed here.

    This test is the reason the coercion exists. If the frontend ever widens to
    accept numbers, this fails and whoever changed it gets to decide
    deliberately rather than by accident.
    """
    schema = Path(__file__).resolve().parents[3] / "apps/web/lib/api/arenaSchemas.ts"
    if not schema.is_file():  # pragma: no cover - partial checkouts
        pytest.skip("web schema not present in this checkout")

    src = schema.read_text()
    block = re.search(r"const persistedResponseSchema = z\.object\(\{(.*?)\}\)", src, re.DOTALL)
    assert block, "persistedResponseSchema not found"
    assert re.search(r"\bid:\s*z\.string\(\)", block.group(1)), (
        "frontend no longer requires a string id; revisit the server-side coercion"
    )


def test_integer_primary_key_is_emitted_as_a_string():
    item = _serialize(4321)
    assert item["id"] == "4321"
    assert isinstance(item["id"], str)
    # json round-trip is what actually reaches Zod
    assert isinstance(json.loads(json.dumps(item))["id"], str)


def test_response_id_falls_back_to_a_string_id():
    """The fallback path used to smuggle the same int in under another key."""
    item = _serialize(99, response_id=None)
    assert item["response_id"] == "99"
    assert isinstance(item["response_id"], str)


def test_explicit_response_id_is_preserved():
    item = _serialize(7, response_id="resp-abc")
    assert item["response_id"] == "resp-abc"
    assert item["id"] == "7"


def test_absent_id_stays_null_rather_than_the_string_none():
    """str(None) == 'None' would pass z.string() and poison the data instead."""
    item = _serialize(None)
    assert item["id"] is None
