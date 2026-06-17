"""Shared async HTTP client registry for provider connections.

FH106: Reuses long-lived httpx.AsyncClient instances per provider instead of
creating per-call clients. Connection pooling, keep-alive, bounded connections.

Usage:
    from model_gateway.http_clients import get_provider_client, close_all_clients
"""

from __future__ import annotations

import logging
import asyncio
from typing import AsyncIterator

import httpx

logger = logging.getLogger("model_gateway.http_clients")

_clients: dict[str, httpx.AsyncClient] = {}
_lock = asyncio.Lock()

_DEFAULT_TIMEOUT = httpx.Timeout(
    connect=5.0,
    read=60.0,
    write=5.0,
    pool=5.0,
)

_DEFAULT_LIMITS = httpx.Limits(
    max_connections=20,
    max_keepalive_connections=10,
    keepalive_expiry=30,
)


async def get_provider_client(provider: str = "default") -> httpx.AsyncClient:
    """Get or create a shared httpx.AsyncClient for the given provider.

    Clients are created lazily and reused across calls. They auto-close on
    application shutdown via close_all_clients().
    """
    async with _lock:
        if provider in _clients and not _clients[provider].is_closed:
            return _clients[provider]

        client = httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT,
            limits=_DEFAULT_LIMITS,
            headers={"User-Agent": "Consultaion/1.0"},
        )
        _clients[provider] = client
        logger.debug("Created shared httpx client for provider=%s", provider)
        return client


async def close_all_clients() -> None:
    """Close all shared httpx clients. Call during application shutdown."""
    async with _lock:
        for provider, client in list(_clients.items()):
            if not client.is_closed:
                try:
                    await client.aclose()
                    logger.debug("Closed httpx client for provider=%s", provider)
                except Exception as e:
                    logger.warning("Error closing httpx client for %s: %s", provider, e)
        _clients.clear()


def get_client_stats() -> dict[str, bool]:
    """Return current client state for diagnostics."""
    return {p: not c.is_closed for p, c in _clients.items()}
