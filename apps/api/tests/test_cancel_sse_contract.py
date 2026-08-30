import sse_backend
import sse_execution_guard
from sse_terminal_contract import install_cancelled_terminal_event


install_cancelled_terminal_event()


def test_cancelled_is_a_terminal_critical_sse_event():
    assert "cancelled" in sse_backend.TERMINAL_EVENT_TYPES
    assert "cancelled" in sse_backend.CRITICAL_EVENT_TYPES
    assert "cancelled" in sse_execution_guard._STREAM_TERMINAL_EVENTS
