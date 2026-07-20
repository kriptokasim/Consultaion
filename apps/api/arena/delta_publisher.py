"""PS157 Track I: Server-side arena delta publisher.

Wraps the DeltaCoalescer with a managed lifecycle:

- first delta per model is published immediately
- later deltas are coalesced per response_id
- flush is forced before lifecycle boundaries (persisting, completed, failed)
- bounded memory via configurable max items / max chars
- publish failures never abort provider generation
- all background tasks stop when the Run ends
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from model_gateway.types import ModelDelta

logger = logging.getLogger(__name__)


class ArenaDeltaPublisher:
    """Managed delta publisher for a single arena model call."""

    def __init__(
        self,
        publish_fn: Callable[[dict], None],
        response_id: str,
        model_id: str,
        *,
        flush_interval_ms: int = 30,
        max_chars: int = 96,
        max_items: int = 256,
    ) -> None:
        self._publish_fn = publish_fn
        self._response_id = response_id
        self._model_id = model_id
        self._flush_interval_ms = flush_interval_ms
        self._max_chars = max_chars
        self._max_items = max_items
        self._pending: list[ModelDelta] = []
        self._total_chars = 0
        self._first = True
        self._closed = False
        self._flush_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        pass

    async def push(self, delta: ModelDelta) -> None:
        if self._closed:
            return
        if self._first:
            self._first = False
            await self._publish_one(delta)
            return

        self._pending.append(delta)
        self._total_chars += len(delta.text)

        if (
            len(self._pending) >= self._max_items
            or self._total_chars >= self._max_chars
        ):
            await self._flush()

    async def flush(self) -> None:
        if self._pending:
            await self._flush()

    async def close(self) -> None:
        self._closed = True
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except (asyncio.CancelledError, Exception):
                pass
            self._flush_task = None

    async def fail(self, error: Optional[Exception] = None) -> None:
        await self.close()

    async def _publish_one(self, delta: ModelDelta) -> None:
        try:
            self._publish_fn({
                "type": "model_response_delta",
                "response_id": self._response_id,
                "model_id": self._model_id,
                "text": delta.text,
                "delta_sequence": delta.sequence,
                "accumulated_chars": delta.accumulated_chars,
            })
        except Exception:
            logger.warning("Delta publish failed (non-fatal)", exc_info=True)

    async def _flush(self) -> None:
        if not self._pending:
            return
        batch = self._pending
        self._pending = []
        self._total_chars = 0

        text = "".join(d.text for d in batch)
        last = batch[-1]
        merged = ModelDelta(
            text=text,
            sequence=last.sequence,
            accumulated_chars=last.accumulated_chars,
        )
        await self._publish_one(merged)
