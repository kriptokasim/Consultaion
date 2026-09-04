"""Centralize terminal SSE event compatibility for cancellation."""

from __future__ import annotations


def install_cancelled_terminal_event() -> None:
    """Extend both SSE layers with the cancellation terminal contract."""
    import sse_backend
    import sse_execution_guard

    cancelled = "cancelled"
    sse_backend.TERMINAL_EVENT_TYPES = frozenset(
        set(sse_backend.TERMINAL_EVENT_TYPES) | {cancelled}
    )
    sse_backend.CRITICAL_EVENT_TYPES = (
        sse_backend.TERMINAL_EVENT_TYPES | sse_backend.CRITICAL_NON_TERMINAL_EVENT_TYPES
    )
    sse_execution_guard._STREAM_TERMINAL_EVENTS = frozenset(
        set(sse_execution_guard._STREAM_TERMINAL_EVENTS) | {cancelled}
    )


def install_sse_ordering() -> None:
    """Install the publication-order fence before serving debate traffic."""
    from sse_ordering_guard import install_sse_ordering_guard

    install_sse_ordering_guard()


install_sse_ordering()
