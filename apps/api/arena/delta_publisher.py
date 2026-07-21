"""PS157 Track I: Server-side arena delta publisher.

Managed lifecycle per model call:

- first delta published immediately
- later deltas coalesced per response_id
- flush forced before lifecycle boundaries
- bounded memory: flush (never drop) when max items/chars hit
- publish failures never abort provider generation
- close() flushes pending then stops timer
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Awaitable, Callable, Optional, Union

from model_gateway.types import ModelDelta

logger = logging.getLogger(__name__)

PublishFn = Callable[[dict], Union[None, Awaitable[None]]]


class ArenaDeltaPublisher:
    """Managed delta publisher for a single arena model call."""

    def __init__(
        self,
        publish_fn: PublishFn,
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
        if self._flush_task is not None:
            return
        self._flush_task = asyncio.create_task(self._timer_loop())

    async def _timer_loop(self) -> None:
        interval = self._flush_interval_ms / 1000.0
        try:
            while not self._closed:
                await asyncio.sleep(interval)
                if self._pending and not self._closed:
                    await self._flush()
        except asyncio.CancelledError:
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
        if self._pending:
            await self._flush()

    async def fail(self, error: Optional[Exception] = None) -> None:
        await self.close()

    async def _call_publish(self, event: dict) -> None:
        result = self._publish_fn(event)
        if inspect.isawaitable(result):
            await result

    async def _publish_one(self, delta: ModelDelta) -> None:
        try:
            await self._call_publish({
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
