from collections import defaultdict
from threading import Lock
from typing import Dict

_metrics: Dict[str, int] = defaultdict(int)
_lock = Lock()


def increment_metric(name: str, value: int = 1) -> None:
    with _lock:
        _metrics[name] += value


def get_metrics_snapshot() -> Dict[str, int]:
    with _lock:
        return dict(_metrics)
