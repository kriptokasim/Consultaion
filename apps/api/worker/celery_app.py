from __future__ import annotations

import json
import logging
import os
import time

from config import settings

logger = logging.getLogger(__name__)

_GIT_SHA = os.environ.get("GIT_SHA", "unknown")
_WORKER_ID = os.environ.get("CELERY_WORKER_HOSTNAME", os.environ.get("HOSTNAME", "unknown"))

try:
    from celery import Celery
    from celery.schedules import crontab
except ImportError:  # pragma: no cover - allow tests without celery installed
    crontab = None

    class _EagerConfig(dict):
        def __getattr__(self, item):
            return self.get(item)

        def __setattr__(self, key, value):
            self[key] = value

    class Celery:  # type: ignore
        def __init__(self, _name: str, broker: str | None = None, backend: str | None = None):
            self.name = _name
            self.broker = broker
            self.backend = backend
            self.conf: _EagerConfig = _EagerConfig()

        def task(self, name: str | None = None, bind: bool = False, max_retries: int = 0, **_: object):
            def decorator(func):
                class EagerTask:
                    __name__ = name or getattr(func, "__name__", "task")

                    def delay(self, *args, **kwargs):
                        return self(*args, **kwargs)

                    def apply(self, args=None, kwargs=None):
                        args = args or ()
                        kwargs = kwargs or {}
                        return self(*args, **kwargs)

                    def retry(self, exc=None, countdown=None):  # pragma: no cover - fallback
                        raise exc or RuntimeError("Task retry requested in eager mode")

                    def __call__(self, *args, **kwargs):
                        if bind:
                            return func(self, *args, **kwargs)
                        return func(*args, **kwargs)

                return EagerTask()

            return decorator

broker_url = settings.CELERY_BROKER_URL or "memory://"
result_backend = settings.CELERY_RESULT_BACKEND or broker_url or "cache+memory://"

celery_app = Celery(
    "consultaion_worker",
    broker=broker_url,
    backend=result_backend,
)


def _write_worker_heartbeat():
    """Write worker heartbeat to Redis for ops visibility."""
    try:
        from redis_pool import get_sync_redis_client
        redis_client = get_sync_redis_client()
        if not redis_client:
            return

        queue_names = []
        task_routes = getattr(celery_app.conf, "task_routes", None) or {}
        if isinstance(task_routes, dict):
            seen = set()
            for route in task_routes.values():
                q = route.get("queue") if isinstance(route, dict) else None
                if q and q not in seen:
                    seen.add(q)
                    queue_names.append(q)
        if not queue_names:
            queue_names = [getattr(celery_app.conf, "task_default_queue", "default")]

        heartbeat = {
            "timestamp": time.time(),
            "git_sha": _GIT_SHA,
            "worker_id": _WORKER_ID,
            "queue_names": queue_names,
            "providers": {
                "openai": bool(settings.OPENAI_API_KEY),
                "anthropic": bool(settings.ANTHROPIC_API_KEY),
                "gemini": bool(settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY),
                "openrouter": bool(settings.OPENROUTER_API_KEY),
                "groq": bool(settings.GROQ_API_KEY),
                "mistral": bool(settings.MISTRAL_API_KEY),
            },
        }
        redis_client.set(
            f"worker:heartbeat:{_WORKER_ID}",
            json.dumps(heartbeat),
            ex=120,
        )
    except Exception as e:
        logger.warning("Failed to write worker heartbeat: %s", e)


if hasattr(celery_app, "conf") and hasattr(celery_app.conf, "update"):
    beat_schedule = {}
    if crontab is not None:
        beat_schedule = {
            "billing-reconcile-daily": {
                "task": "billing.reconcile_previous_day",
                "schedule": crontab(hour=3, minute=0),
            },
            "billing-reconcile-monthly": {
                "task": "billing.reconcile_current_period",
                "schedule": crontab(hour=4, minute=0, day_of_month=1),
            },
            "worker-heartbeat": {
                "task": "worker.heartbeat_tick",
                "schedule": 30.0,
            },
        }
    else:
        beat_schedule = {
            "billing-reconcile-daily": {
                "task": "billing.reconcile_previous_day",
                "schedule": {"hour": 3, "minute": 0},
            },
            "billing-reconcile-monthly": {
                "task": "billing.reconcile_current_period",
                "schedule": {"day_of_month": 1, "hour": 4, "minute": 0},
            },
            "worker-heartbeat": {
                "task": "worker.heartbeat_tick",
                "schedule": 30.0,
            },
        }

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        beat_schedule=beat_schedule,
        # Three-queue routing
        task_routes={
            "arena.*": {"queue": "interactive"},
            "debate.*": {"queue": "interactive"},
            "voting.*": {"queue": "interactive"},
            "coding.*": {"queue": "interactive"},
            "billing.*": {"queue": "maintenance"},
            "maintenance.*": {"queue": "maintenance"},
        },
        task_default_queue="default",
    )


# Register heartbeat task
if hasattr(celery_app, "task"):
    @celery_app.task(name="worker.heartbeat_tick", bind=False)
    def heartbeat_tick():
        _write_worker_heartbeat()

# Write initial heartbeat on import
_write_worker_heartbeat()
