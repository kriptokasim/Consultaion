"""Patchset 148 I1: Structured logging helpers.

Provides consistent, machine-parseable log output for critical backend events.
Prefer these over raw `logger.exception()` calls to ensure correlation IDs,
debate/model context, and structured extras are always included.
"""
from __future__ import annotations

import logging
from typing import Any


def log_exception(
    logger: logging.Logger,
    message: str,
    *,
    exc_info: bool = True,
    correlation_id: str | None = None,
    debate_id: str | None = None,
    model_id: str | None = None,
    user_id: str | None = None,
    **fields: Any,
) -> None:
    """Log an exception with structured context fields.

    Usage::

        from utils.log_helpers import log_exception

        try:
            ...
        except Exception as exc:
            log_exception(
                logger, "Model call failed",
                debate_id=debate_id,
                model_id=model_id,
                correlation_id=ctx.correlation_id,
            )

    All keyword arguments are merged into the ``extra`` dict for structured
    log aggregators (Datadog, CloudWatch, etc.).
    """
    extra: dict[str, Any] = {}
    if correlation_id:
        extra["correlation_id"] = correlation_id
    if debate_id:
        extra["debate_id"] = debate_id
    if model_id:
        extra["model_id"] = model_id
    if user_id:
        extra["user_id"] = user_id
    extra.update(fields)

    logger.exception(message, extra=extra, exc_info=exc_info)


def log_warning(
    logger: logging.Logger,
    message: str,
    *,
    correlation_id: str | None = None,
    debate_id: str | None = None,
    model_id: str | None = None,
    user_id: str | None = None,
    **fields: Any,
) -> None:
    """Log a warning with structured context fields."""
    extra: dict[str, Any] = {}
    if correlation_id:
        extra["correlation_id"] = correlation_id
    if debate_id:
        extra["debate_id"] = debate_id
    if model_id:
        extra["model_id"] = model_id
    if user_id:
        extra["user_id"] = user_id
    extra.update(fields)

    logger.warning(message, extra=extra)
