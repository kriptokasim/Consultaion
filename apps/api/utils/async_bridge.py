"""Bridge blocking database work off the event loop without losing context.

``loop.run_in_executor`` dispatches to a worker thread, and a worker thread
does not inherit the caller's :mod:`contextvars` context. Anything the wrapped
callable reads from a ContextVar — the bound :class:`ExecutionLease` that
fences orchestrated writes, the gateway attempt context used for usage
accounting — is therefore absent inside the thread, and fenced writes fail
closed with "no execution lease bound to this context".

:func:`run_blocking` copies the current context and runs the callable inside
it, so a synchronous session block behaves the same whether it runs inline or
on the executor.
"""

from __future__ import annotations

import asyncio
import contextvars
from typing import Any, Callable, TypeVar

T = TypeVar("T")


async def run_blocking(fn: Callable[..., T], *args: Any) -> T:
    """Run ``fn(*args)`` on the default executor under the current context."""
    ctx = contextvars.copy_context()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ctx.run(fn, *args))
