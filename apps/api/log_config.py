import json
import logging
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any, Dict

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
log_context_ctx: ContextVar[Dict[str, Any]] = ContextVar("log_context", default={})


def set_request_id(request_id: str) -> Token:
    return request_id_ctx.set(request_id)


def get_request_id() -> str:
    return request_id_ctx.get("-")


def reset_request_id(token: Token) -> None:
    request_id_ctx.reset(token)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        payload.update(get_log_context())
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def get_log_context() -> Dict[str, Any]:
    return dict(log_context_ctx.get({}))  # copy to avoid mutation leaks


def update_log_context(**kwargs: Any) -> Dict[str, Any]:
    current = get_log_context()
    updates = {key: value for key, value in kwargs.items() if value is not None}
    if not updates:
        return current
    current.update(updates)
    log_context_ctx.set(current)
    return current


def clear_log_context() -> None:
    log_context_ctx.set({})


from config import settings

class DevFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", "-")
        msg = record.getMessage()
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)
        return f"[{datetime.now().strftime('%H:%M:%S')}] {record.levelname} [{request_id}] {record.name}: {msg}"


def log_event(event_name: str, level: int = logging.INFO, **kwargs: Any) -> None:
    """
    Log a structured event.
    Usage: log_event("debate.created", debate_id="123", user_id="456")
    """
    logger = logging.getLogger("apps.event")
    req_id = get_request_id()
    payload = {"event": event_name, "request_id": req_id, **kwargs}
    # In dev, we might want to see the event name clearly
    if settings.IS_LOCAL_ENV:
        logger.log(level, f"Event: {event_name} {json.dumps(kwargs, default=str)}")
    else:
        # In prod, the JsonFormatter will pick up the extra fields if we pass them via extra
        # But standard python logging 'extra' merges into the record, which JsonFormatter can read.
        # However, our JsonFormatter reads from record.__dict__ or we can pass a dict as message.
        # Let's stick to passing a dict as message for simplicity if we want strict JSON structure,
        # OR update JsonFormatter to merge 'extra'.
        # For now, let's update the context or just log the dict.
        # Better approach: update log context temporarily or just log the payload.
        logger.log(level, json.dumps(payload, default=str))


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "log_config.RequestIdFilter",
        }
    },
    "formatters": {
        "json": {
            "()": "log_config.JsonFormatter",
        },
        "dev": {
            "()": "log_config.DevFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "dev" if settings.IS_LOCAL_ENV else "json",
            "filters": ["request_id"],
        }
    },
    "loggers": {
        "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": settings.LOG_LEVEL, "propagate": False},
        "": {"handlers": ["console"], "level": "INFO"},
    },
}
