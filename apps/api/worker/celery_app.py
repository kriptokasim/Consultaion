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
    from kombu import Queue
except ImportError:  # pragma: no cover - allow tests without celery installed
    crontab = None
    Queue = None  # type: ignore[assignment,misc]

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


# Explicit production task inventory. The worker is launched as
# ``celery -A worker.celery_app worker``; Celery does not discover arbitrary
# modules merely because task_routes contain their name prefixes. Every module
# that owns @celery_app.task registrations must therefore be imported by the
# worker at boot or queued tasks can be rejected as "unregistered task".
PRODUCTION_TASK_MODULES: tuple[str, ...] = (
    "worker.billing_tasks",
    "worker.debate_tasks",
    "worker.arena_tasks",
    "worker.coding_tasks",
    "worker.voting_tasks",
)


def configured_worker_queue_names(settings_obj=settings) -> tuple[str, ...]:
    """Return every queue this worker may receive work on.

    Debate dispatch queue names are configurable, so the worker declaration
    must be derived from the same settings rather than a hard-coded Compose
    command. ``dict.fromkeys`` preserves priority while removing aliases.
    """

    candidates = (
        settings_obj.DEBATE_FAST_QUEUE_NAME,
        settings_obj.DEBATE_DEEP_QUEUE_NAME,
        settings_obj.DEBATE_DEFAULT_QUEUE,
        settings_obj.CELERY_INTERACTIVE_QUEUE,
        "maintenance",
        "default",
    )
    return tuple(
        dict.fromkeys(
            name.strip()
            for name in candidates
            if isinstance(name, str) and name.strip()
        )
    )


WORKER_QUEUE_NAMES = configured_worker_queue_names()


def _write_worker_heartbeat():
    """Write worker heartbeat to Redis for ops visibility."""
    try:
        from redis_pool import get_sync_redis_client
        redis_client = get_sync_redis_client()
        if not redis_client:
            return

        heartbeat = {
            "timestamp": time.time(),
            "git_sha": _GIT_SHA,
            "worker_id": _WORKER_ID,
            "queue_names": list(WORKER_QUEUE_NAMES),
            "task_modules": list(PRODUCTION_TASK_MODULES),
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
            "billing-reconcile-terminal-hosted-credits": {
                "task": "billing.reconcile_terminal_hosted_credits",
                "schedule": 300.0,
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
            "billing-reconcile-terminal-hosted-credits": {
                "task": "billing.reconcile_terminal_hosted_credits",
                "schedule": 300.0,
            },
            "worker-heartbeat": {
                "task": "worker.heartbeat_tick",
                "schedule": 30.0,
            },
        }

    interactive_queue = settings.CELERY_INTERACTIVE_QUEUE or "interactive"
    declared_queues = (
        tuple(Queue(name) for name in WORKER_QUEUE_NAMES)
        if Queue is not None
        else WORKER_QUEUE_NAMES
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        imports=PRODUCTION_TASK_MODULES,
        beat_schedule=beat_schedule,
        task_queues=declared_queues,
        task_routes={
            "arena.*": {"queue": interactive_queue},
            "debate.*": {"queue": interactive_queue},
            "debates.*": {"queue": interactive_queue},
            "voting.*": {"queue": interactive_queue},
            "coding.*": {"queue": interactive_queue},
            "billing.*": {"queue": "maintenance"},
            "maintenance.*": {"queue": "maintenance"},
        },
        task_default_queue="default",
    )


if hasattr(celery_app, "task"):
    @celery_app.task(name="worker.heartbeat_tick", bind=False)
    def heartbeat_tick():
        _write_worker_heartbeat()


_write_worker_heartbeat()

# Keep worker bootstrap limited to guards that must exist before any task-level
# LLM call. Runtime exception/credential-scope hardening is required before the
# legacy Agent pre-router path can inspect provider health; heavy terminal
# accounting remains owned by worker.debate_tasks.
try:
    from model_gateway.runtime_exception_guard import install_runtime_exception_guard
    from sse_terminal_guard import install_terminal_commit_guard

    install_runtime_exception_guard()
    install_terminal_commit_guard()
except Exception:  # pragma: no cover - worker startup must surface this in prod
    logger.exception("Could not install required worker runtime guards")
    if settings.APP_ENV in {"production", "staging"}:
        raise
