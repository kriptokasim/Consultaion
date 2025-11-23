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
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_id"],
        }
    },
    "loggers": {
        "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "": {"handlers": ["console"], "level": "INFO"},
    },
}
