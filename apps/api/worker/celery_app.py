from __future__ import annotations

from config import settings

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
        }

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        beat_schedule=beat_schedule,
    )
