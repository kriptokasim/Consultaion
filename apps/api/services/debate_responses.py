"""
Canonical Persisted Responses Service (PR-FH89).

Queries `Message` rows directly for a debate, normalizes historical
response roles into a single DTO, and never silently converts query
failures into empty results.

Public vs private handling:
- private (owner/admin): full failure metadata, retryability, http_status
- public: content only when debate.is_public, safe failure labels only,
  no internal provider detail, no raw exception text.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlmodel import Session

from models import Debate, Message

logger = logging.getLogger(__name__)


# Roles treated as model answers in the canonical responses contract.
RESPONSE_ROLES = {
    "arena_response",
    "seat",
    "delegate",
    "candidate",
    "revised",
}

# Roles that must NEVER appear as model answers (synthesis, judging, pipeline).
EXCLUDED_ROLES = {
    "arena_synthesis",
    "final",
    "judge",
    "system",
    "notice",
}


@dataclass
class ResponsesSummary:
    expected: int
    persisted: int
    successful: int
    failed: int


class ResponsesQueryError(RuntimeError):
    """Raised when the persisted-responses query itself fails.

    Callers should convert this to a non-2xx response. We never want
    this to be coerced into a successful empty list.
    """


def _getattr_safely(obj: Any, *path: str, default: Any = None) -> Any:
    cur: Any = obj
    for key in path:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return default if cur is None else cur


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "t"}
    return False


def _extract_attempt_count(meta: Dict[str, Any]) -> int:
    value = _getattr_safely(meta, "attempt_count", default=0)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _expected_model_count(debate: Debate) -> int:
    """Best-effort count of expected models for a debate.

    Order of preference:
    1. final_meta.total_count
    2. config.models length
    3. panel_config panel size
    4. 0 (unknown)
    """
    final_meta = debate.final_meta or {}
    total = _getattr_safely(final_meta, "total_count")
    if isinstance(total, int) and total > 0:
        return total

    config = debate.config or {}
    models = config.get("models") or []
    if isinstance(models, list) and models:
        return len(models)

    panel = debate.panel_config or {}
    panel_models = panel.get("models") or panel.get("panel") or []
    if isinstance(panel_models, list) and panel_models:
        return len(panel_models)

    return 0


def _normalize_message(msg: Message, *, is_public: bool) -> Dict[str, Any]:
    """Convert a Message ORM row into the canonical DTO dict."""
    meta = msg.meta if isinstance(msg.meta, dict) else {}

    model_id = _getattr_safely(meta, "model_id", default=msg.persona) or msg.persona or "unknown"
    display_name = (
        _getattr_safely(meta, "display_name")
        or _getattr_safely(meta, "model_display_name")
        or model_id
    )
    provider = _getattr_safely(meta, "provider") or "ai"
    role = msg.role or "arena_response"
    response_type = role if role in RESPONSE_ROLES else "arena_response"

    success_flag = _coerce_bool(_getattr_safely(meta, "success", default=True))
    error_code = _getattr_safely(meta, "error_code")
    error_message = _getattr_safely(meta, "safe_error") or _getattr_safely(meta, "error_message")
    retryable = _coerce_bool(_getattr_safely(meta, "retryable", default=False))
    error_http_status = _getattr_safely(meta, "error_http_status")

    content = msg.content or _getattr_safely(meta, "content") or _getattr_safely(meta, "text") or ""

    item: Dict[str, Any] = {
        "id": msg.id,
        "debate_id": msg.debate_id,
        "response_type": response_type,
        "role": role,
        "round": int(msg.round or 0),
        "model_id": model_id,
        "display_name": display_name,
        "provider": provider,
        "content": content,
        "success": success_flag,
        "error_code": error_code,
        "error_message": error_message,
        "retryable": retryable,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "metadata": {
            "logo_url": _getattr_safely(meta, "logo_url"),
            "persona_type": _getattr_safely(meta, "persona_type"),
            "persona_tagline": _getattr_safely(meta, "persona_tagline"),
            "attempt_count": _extract_attempt_count(meta),
        },
    }

    if is_public:
        # Public DTO: drop internal provider detail, never expose raw exception text.
        item["error_code"] = None
        item["error_message"] = None
        item["retryable"] = False
        item.pop("error_http_status", None)
        # Replace content with a bounded safe message for failed public responses.
        if not success_flag:
            safe = "This model could not respond."
            item["content"] = safe
        item["metadata"] = {
            k: v for k, v in item["metadata"].items()
            if k in {"logo_url", "persona_type", "persona_tagline"}
        }

    return item


def fetch_persisted_responses(
    session: Session,
    debate: Debate,
    *,
    is_public: bool,
) -> Dict[str, Any]:
    """Query persisted Message rows and return the canonical contract.

    Raises ResponsesQueryError on database failure so the route handler can
    return a non-2xx response. Never coerces failures into `items: []`.
    """
    try:
        stmt = (
            select(Message)
            .where(Message.debate_id == debate.id)
            .where(Message.role.in_(sorted(RESPONSE_ROLES)))
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        messages: List[Message] = list(session.exec(stmt).all())
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to query persisted responses for debate %s", debate.id
        )
        raise ResponsesQueryError(str(exc)) from exc

    items = [_normalize_message(m, is_public=is_public) for m in messages]

    successful = sum(1 for it in items if it["success"])
    failed = len(items) - successful
    expected = _expected_model_count(debate)
    if expected <= 0:
        expected = len(items)

    return {
        "items": items,
        "summary": {
            "expected": expected,
            "persisted": len(items),
            "successful": successful,
            "failed": failed,
        },
    }
