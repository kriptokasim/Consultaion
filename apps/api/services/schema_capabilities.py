from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import inspect, text
from sqlmodel import Session

API_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_DIR = API_ROOT / "alembic"


@dataclass
class SchemaCapabilities:
    has_stage_checkpoint_table: bool = False
    has_stage_checkpoint_attempt_column: bool = False
    has_continuation_table: bool = False
    has_pairwise_vote_table: bool = False
    has_score_table: bool = False
    has_message_table: bool = False
    is_at_alembic_head: bool = False
    inspection_succeeded: bool = False

    missing_capabilities: list[str] = field(default_factory=list)


class SchemaCapabilityRegistry:
    def __init__(self, cache_ttl_seconds: int = 30):
        self._cache: dict[str, tuple[SchemaCapabilities, datetime]] = {}
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)

    def get_cached(self, cache_key: str) -> Optional[SchemaCapabilities]:
        entry = self._cache.get(cache_key)
        if entry:
            caps, ts = entry
            if datetime.now(timezone.utc) - ts < self._cache_ttl:
                return caps
            del self._cache[cache_key]
        return None

    def set_cached(self, cache_key: str, caps: SchemaCapabilities) -> None:
        self._cache[cache_key] = (caps, datetime.now(timezone.utc))

    def invalidate(self, cache_key: Optional[str] = None) -> None:
        if cache_key:
            self._cache.pop(cache_key, None)
        else:
            self._cache.clear()


def _build_cache_key(session: Session) -> str:
    """Build a cache key from stable database identity information."""
    try:
        bind = session.get_bind()
        dialect = bind.dialect.name
        url = bind.url.render_as_string(hide_password=True)
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
        return f"{dialect}:{url_hash}"
    except Exception:
        return "default"


def _check_table_exists(session: Session, table_name: str) -> bool:
    inspector = inspect(session.get_bind())
    return table_name in inspector.get_table_names()


def _check_column_exists(session: Session, table_name: str, column_name: str) -> bool:
    inspector = inspect(session.get_bind())
    try:
        columns = [c["name"] for c in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def _check_alembic_head(session: Session) -> bool:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(ALEMBIC_DIR))
        script = ScriptDirectory.from_config(alembic_cfg)
        heads = script.get_heads()
        if len(heads) != 1:
            return False

        result = session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
        if not result:
            return False
        return str(result) == heads[0]
    except Exception:
        return False


def get_schema_capabilities(
    session: Session,
    registry: Optional[SchemaCapabilityRegistry] = None,
) -> SchemaCapabilities:
    cache_key = _build_cache_key(session)
    if registry:
        cached = registry.get_cached(cache_key)
        if cached:
            return cached

    try:
        has_checkpoint_table = _check_table_exists(session, "debate_stage_checkpoint")
        has_checkpoint_attempt = False
        if has_checkpoint_table:
            has_checkpoint_attempt = _check_column_exists(
                session, "debate_stage_checkpoint", "attempt"
            )

        caps = SchemaCapabilities(
            has_stage_checkpoint_table=has_checkpoint_table,
            has_stage_checkpoint_attempt_column=has_checkpoint_attempt,
            has_continuation_table=_check_table_exists(session, "debate_continuation"),
            has_pairwise_vote_table=_check_table_exists(session, "pairwise_vote"),
            has_score_table=_check_table_exists(session, "score"),
            has_message_table=_check_table_exists(session, "message"),
            is_at_alembic_head=_check_alembic_head(session),
            inspection_succeeded=True,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("schema_inspection_failed error=%s", exc)
        caps = SchemaCapabilities(inspection_succeeded=False)

    missing = []
    if not caps.has_stage_checkpoint_table:
        missing.append("stage_checkpoints")
    if not caps.has_continuation_table:
        missing.append("continuations")
    if not caps.has_pairwise_vote_table:
        missing.append("pairwise_votes")
    if not caps.has_score_table:
        missing.append("scores")
    if not caps.has_message_table:
        missing.append("messages")
    if not caps.is_at_alembic_head:
        missing.append("schema_behind_head")
    caps.missing_capabilities = missing

    if registry:
        registry.set_cached(cache_key, caps)

    return caps


_registry: Optional[SchemaCapabilityRegistry] = None


def get_registry() -> SchemaCapabilityRegistry:
    global _registry
    if _registry is None:
        _registry = SchemaCapabilityRegistry()
    return _registry
