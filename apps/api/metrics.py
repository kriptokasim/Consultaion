from collections import defaultdict
from threading import Lock
from typing import Dict

# Standardized Metric Names (Patchset 107)
# - debate.started
# - debate.completed
# - debate.failed
# - debate.degraded
# - sse.stream.opened
# - sse.stream.closed
# - sse.publish.failed
# - rate_limit.triggered

_metrics: Dict[str, int] = defaultdict(int)
_lock = Lock()


def increment_metric(name: str, value: int = 1) -> None:
    with _lock:
        _metrics[name] += value


def get_metrics_snapshot() -> Dict[str, int]:
    with _lock:
        return dict(_metrics)
