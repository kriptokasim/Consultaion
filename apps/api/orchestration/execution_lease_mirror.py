"""Fast Redis mirror of the database execution-lease fencing identity.

The Debate row remains authoritative. This mirror exists only to let hot SSE
delta publication verify ``owner_id + lease_epoch`` without issuing a database
SELECT for every streamed chunk.

Safety properties:
- mirror TTL is deliberately shorter than the database lease, so an old mirror
  cannot remain valid after the DB row becomes takeover-eligible;
- a mismatched mirror is a definite stale-owner signal;
- a missing/unavailable mirror is *not* treated as ownership proof and callers
  must fall back to the database;
- release is compare-and-delete, never a blind delete of a newer owner's key.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)

MIRROR_SAFETY_MARGIN_SECONDS = 2

_DELETE_IF_OWNER_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


class MirrorVerification(Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


def mirror_key(debate_id: str) -> str:
    return f"execution:lease:{debate_id}"


def mirror_value(lease) -> str:
    return f"{lease.owner_id}|{int(lease.lease_epoch)}"


def _safe_ttl(seconds: float) -> int:
    return max(1, int(math.floor(seconds)) - MIRROR_SAFETY_MARGIN_SECONDS)


async def publish_execution_lease_mirror(lease, *, lease_seconds: float) -> bool:
    """Best-effort publish after DB ownership has already been proven."""
    ttl = _safe_ttl(lease_seconds)
    try:
        from redis_pool import get_async_redis_client

        client = get_async_redis_client()
        if client is None:
            return False
        await client.set(mirror_key(lease.debate_id), mirror_value(lease), ex=ttl)
        return True
    except Exception:
        # Missing mirror only forces the SSE path back to DB authority; it must
        # never make a valid DB lease fail merely because Redis restarted.
        logger.warning(
            "execution_lease.mirror_publish_failed debate_id=%s owner=%s epoch=%s",
            lease.debate_id,
            lease.owner_id,
            lease.lease_epoch,
            exc_info=True,
        )
        return False


async def publish_execution_lease_mirror_until(lease, expires_at: datetime) -> bool:
    """Repair a missing mirror from a DB-verified absolute lease expiry."""
    now = datetime.now(timezone.utc)
    expiry = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=timezone.utc)
    remaining = (expiry - now).total_seconds()
    if remaining <= MIRROR_SAFETY_MARGIN_SECONDS:
        return False
    return await publish_execution_lease_mirror(lease, lease_seconds=remaining)


async def verify_execution_lease_mirror(lease) -> MirrorVerification:
    """Return MATCH/MISMATCH/UNKNOWN without treating Redis absence as proof."""
    try:
        from redis_pool import get_async_redis_client

        client = get_async_redis_client()
        if client is None:
            return MirrorVerification.UNKNOWN
        value = await client.get(mirror_key(lease.debate_id))
        if value is None:
            return MirrorVerification.UNKNOWN
        if str(value) == mirror_value(lease):
            return MirrorVerification.MATCH
        return MirrorVerification.MISMATCH
    except Exception:
        logger.warning(
            "execution_lease.mirror_verify_failed debate_id=%s owner=%s epoch=%s",
            lease.debate_id,
            lease.owner_id,
            lease.lease_epoch,
            exc_info=True,
        )
        return MirrorVerification.UNKNOWN


async def delete_execution_lease_mirror(lease) -> None:
    """Remove the mirror only when it still belongs to this exact owner/epoch."""
    try:
        from redis_pool import get_async_redis_client

        client = get_async_redis_client()
        if client is None:
            return
        await client.eval(
            _DELETE_IF_OWNER_LUA,
            1,
            mirror_key(lease.debate_id),
            mirror_value(lease),
        )
    except Exception:
        # TTL is deliberately shorter than DB expiry, so a failed delete cannot
        # remain authoritative past takeover eligibility.
        logger.warning(
            "execution_lease.mirror_delete_failed debate_id=%s owner=%s epoch=%s",
            lease.debate_id,
            lease.owner_id,
            lease.lease_epoch,
            exc_info=True,
        )
