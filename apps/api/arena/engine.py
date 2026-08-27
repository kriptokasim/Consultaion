"""Arena mode engine: fan-out to SOTA models, collect answers, synthesize verdict."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field, replace
from typing import List

from agents import UsageAccumulator, UsageCall, call_llm_for_role
from database_async import async_session_scope
from models import Debate, Message
from observability.latency import (
    PROMETHEUS_AVAILABLE,
    record_connect_latency,
    record_model_latency,
    record_stream_dps,
    record_stream_duration,
    record_ttft,
)
from parliament.model_registry import get_arena_models, resolve_model_info
from sse_backend import get_sse_backend

from arena.prompts import (
    get_compiled_model_prompt,
)

logger = logging.getLogger(__name__)

MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS = 2


async def _publish_lifecycle_best_effort(backend, channel: str, event: dict) -> None:
    """Lifecycle telemetry must never cancel model execution."""
    try:
        await backend.publish(channel, event)
    except Exception:
        logger.warning(
            "arena.lifecycle_publish_failed channel=%s type=%s",
            channel,
            event.get("type"),
            exc_info=True,
        )


def _is_response_identity_conflict(exc: Exception) -> bool:
    """Return true only for the expected durable response collision."""
    orig = getattr(exc, "orig", None)
    constraint = getattr(getattr(orig, "diag", None), "constraint_name", None)
    if constraint == "uq_message_debate_response_id":
        return True
    message = str(orig or exc).lower()
    return "uq_message_debate_response_id" in message or (
        "unique constraint failed" in message
        and "message.debate_id" in message
        and "message.response_id" in message
    )


def _lease_for_arena_write(
    debate_id: str,
    run_attempt: int,
    owner_id: str | None,
    lease_epoch: int | None,
):
    """Resolve the fencing identity; production writes always require one."""
    from orchestration.execution_context import ExecutionLease, get_current_execution_lease

    from config import settings

    lease = get_current_execution_lease()
    if lease is not None:
        return lease
    if owner_id and lease_epoch is not None:
        return ExecutionLease.create(
            debate_id,
            owner_id=owner_id,
            lease_epoch=lease_epoch,
            run_attempt=run_attempt,
        )
    if getattr(settings, "APP_ENV", "local") in {"production", "staging"}:
        raise RuntimeError("Arena write attempted without an execution lease")
    return None


def _derive_model_family(model_info) -> str:
    if model_info.litellm_model and "/" in model_info.litellm_model:
        return model_info.litellm_model.split("/", 1)[1]
    return model_info.id


def _resolve_arena_models_from_panel(panel_config: dict | None):
    """Resolve a durable panel into the ordered Arena execution manifest.

    Legacy clients stored provider IDs and LiteLLM strings while current
    clients store registry IDs.  Resolution canonicalizes both forms and
    deduplicates model identities so response IDs, checkpoints, billing
    counts, SSE events, and UI slots all describe the same execution set.
    A non-empty durable panel is fail-closed: silently dropping even one seat
    would mutate the user's selected and billed execution contract.
    """
    if not isinstance(panel_config, dict):
        return []

    seats = panel_config.get("seats")
    if not isinstance(seats, list):
        return []

    resolved = []
    seen: set[str] = set()
    unresolved: list[str] = []
    for index, seat in enumerate(seats):
        if not isinstance(seat, dict):
            unresolved.append(f"seat[{index}]")
            continue
        model_key = seat.get("model") or seat.get("model_id")
        if not isinstance(model_key, str) or not model_key.strip():
            unresolved.append(f"seat[{index}]")
            continue
        model_info = resolve_model_info(model_key.strip())
        if model_info is None:
            unresolved.append(model_key.strip())
            continue
        if model_info.id in seen:
            logger.info("arena.panel_model_deduplicated model=%s", model_info.id)
            continue
        seen.add(model_info.id)
        resolved.append(model_info)

    if unresolved:
        logger.error(
            "arena.panel_manifest_unresolved unresolved=%s",
            unresolved,
        )
        raise ValueError(
            "Persisted Arena panel contains unresolved model seats: " + ", ".join(unresolved)
        )
    return resolved


def _select_arena_execution_models(panel_config: dict | None):
    """Select the exact stored panel, falling back only for legacy empty data."""
    panel_models = _resolve_arena_models_from_panel(panel_config)
    if panel_models:
        return panel_models
    return get_arena_models()


@dataclass
class ArenaModelResponse:
    """Individual model response in an arena run."""

    model_id: str
    display_name: str
    provider: str
    content: str
    success: bool
    logo_url: str | None = None
    persona_type: str | None = None
    persona_tagline: str | None = None
    error: str | None = None
    error_code: str | None = None
    response_id: str | None = None
    run_attempt: int = 1
    retry_generation: int = 0
    usage_call: UsageCall | None = None


@dataclass
class ArenaSynthesisRevision:
    """Durable provisional/final synthesis snapshot identity."""

    synthesis_id: str
    content: str
    report: dict | None
    response_ids: tuple[str, ...]
    successful_count: int
    total_count: int
    input_hash: str
    revision: int = 0
    status: str = "provisional"
    usage_call: UsageCall | None = None


def _build_synthesis_report_nonfatal(
    *,
    prompt: str,
    content: str,
    model_responses: list[dict],
    debate_id: str,
    synthesis_id: str,
) -> dict | None:
    """Normalize the optional report without invalidating visible synthesis."""
    try:
        from reporting.report_builder import build_report_from_synthesis

        return build_report_from_synthesis(
            prompt,
            content,
            model_responses=model_responses,
        ).model_dump(mode="json")
    except Exception:
        logger.warning(
            "arena.synthesis_report_normalization_failed debate_id=%s synthesis_id=%s",
            debate_id,
            synthesis_id,
            exc_info=True,
        )
        return None


def _message_to_arena_response(message: Message) -> ArenaModelResponse:
    meta = message.meta or {}
    return ArenaModelResponse(
        model_id=meta.get("model_id") or "",
        display_name=message.persona,
        provider=meta.get("provider") or "",
        content=message.content,
        success=meta.get("success", True),
        logo_url=meta.get("logo_url"),
        persona_type=meta.get("persona_type"),
        persona_tagline=meta.get("persona_tagline"),
        error=meta.get("error"),
        error_code=meta.get("error_code"),
        response_id=message.response_id or meta.get("response_id") or str(message.id),
        run_attempt=int(meta.get("run_attempt", 1) or 1),
        retry_generation=int(meta.get("retry_generation", 0) or 0),
        usage_call=_usage_call_from_meta(meta.get("usage_call")),
    )


def _canonical_attempt_responses(
    messages: list[Message],
    *,
    run_attempt: int,
    allowed_model_ids: set[str],
) -> list[ArenaModelResponse]:
    """Return one latest durable response per model for the active attempt."""
    by_model: dict[str, ArenaModelResponse] = {}
    for message in messages:
        response = _message_to_arena_response(message)
        if response.run_attempt != run_attempt or response.model_id not in allowed_model_ids:
            continue
        previous = by_model.get(response.model_id)
        if previous is None or response.retry_generation >= previous.retry_generation:
            by_model[response.model_id] = response
    return list(by_model.values())


def _response_snapshot(
    responses: list[ArenaModelResponse],
    *,
    model_order: dict[str, int],
) -> tuple[str, ...]:
    successful = [response for response in responses if response.success and response.response_id]
    successful.sort(key=lambda response: model_order.get(response.model_id, 999))
    return tuple(response.response_id for response in successful if response.response_id)


def _synthesis_snapshot_hash(
    prompt: str,
    responses: list[ArenaModelResponse],
    *,
    model_order: dict[str, int],
) -> str:
    ordered = sorted(
        (response for response in responses if response.success),
        key=lambda response: model_order.get(response.model_id, 999),
    )
    payload = {
        "prompt": prompt,
        "responses": [
            {
                "response_id": response.response_id,
                "model_id": response.model_id,
                "content": response.content,
            }
            for response in ordered
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _usage_call_to_meta(call: UsageCall | None) -> dict | None:
    if call is None:
        return None
    return {
        "prompt_tokens": float(getattr(call, "prompt_tokens", 0) or 0),
        "completion_tokens": float(getattr(call, "completion_tokens", 0) or 0),
        "total_tokens": float(getattr(call, "total_tokens", 0) or 0),
        "cost_usd": float(getattr(call, "cost_usd", 0) or 0),
        "provider": getattr(call, "provider", None),
        "model": getattr(call, "model", None),
        "gateway": getattr(call, "gateway", None),
        "model_pool": getattr(call, "model_pool", None),
        "routing_policy": getattr(call, "routing_policy", None),
        "fallback_used": bool(getattr(call, "fallback_used", False)),
        "fallback_reason": getattr(call, "fallback_reason", None),
        "user_plan": getattr(call, "user_plan", None),
        "estimated_cost_usd": float(getattr(call, "estimated_cost_usd", 0) or 0),
        "retry_count": int(getattr(call, "retry_count", 0) or 0),
    }


def _usage_call_from_meta(meta: dict | None) -> UsageCall | None:
    if not isinstance(meta, dict):
        return None
    return UsageCall(
        prompt_tokens=float(meta.get("prompt_tokens", 0) or 0),
        completion_tokens=float(meta.get("completion_tokens", 0) or 0),
        total_tokens=float(meta.get("total_tokens", 0) or 0),
        cost_usd=float(meta.get("cost_usd", 0) or 0),
        provider=meta.get("provider"),
        model=meta.get("model"),
        gateway=meta.get("gateway"),
        model_pool=meta.get("model_pool"),
        routing_policy=meta.get("routing_policy"),
        fallback_used=bool(meta.get("fallback_used", False)),
        fallback_reason=meta.get("fallback_reason"),
        user_plan=meta.get("user_plan"),
        estimated_cost_usd=float(meta.get("estimated_cost_usd", 0) or 0),
        retry_count=int(meta.get("retry_count", 0) or 0),
    )


def _usage_call_from_gateway_result(result) -> UsageCall:
    """Normalize streaming gateway usage into the durable Arena contract."""
    return UsageCall(
        prompt_tokens=float(getattr(result, "prompt_tokens", 0) or 0),
        completion_tokens=float(getattr(result, "completion_tokens", 0) or 0),
        total_tokens=float(getattr(result, "total_tokens", 0) or 0),
        cost_usd=float(getattr(result, "cost_usd", 0) or 0),
        provider=getattr(result, "provider", None),
        model=getattr(result, "model_used", None),
        gateway=getattr(result, "gateway", None),
        model_pool=getattr(result, "model_pool", None),
        routing_policy=getattr(result, "routing_policy", None),
        fallback_used=bool(getattr(result, "fallback_used", False)),
        fallback_reason=getattr(result, "fallback_reason", None),
        user_plan=getattr(result, "user_plan", None),
        estimated_cost_usd=float(getattr(result, "estimated_cost_usd", 0) or 0),
        retry_count=int(getattr(result, "retry_count", 0) or 0),
    )


def _synthesis_revision_id(
    debate_id: str,
    run_attempt: int,
    revision: int,
    input_hash: str,
) -> str:
    """Bind revision identity to the immutable response snapshot."""
    return f"synth-{debate_id}-a{run_attempt}-r{revision}-" f"{input_hash[:16]}"


def _message_to_synthesis_revision(message: Message) -> ArenaSynthesisRevision:
    meta = message.meta or {}
    return ArenaSynthesisRevision(
        synthesis_id=message.response_id or meta.get("synthesis_id") or str(message.id),
        content=message.content,
        report=meta.get("synthesis_report"),
        response_ids=tuple(meta.get("response_ids") or ()),
        successful_count=int(meta.get("successful_count", 0) or 0),
        total_count=int(meta.get("total_count", 0) or 0),
        input_hash=str(meta.get("input_hash") or ""),
        revision=int(meta.get("revision", 0) or 0),
        status=str(meta.get("status") or "provisional"),
        usage_call=_usage_call_from_meta(meta.get("usage_call")),
    )


async def _load_synthesis_revision(
    session,
    debate_id: str,
    synthesis_id: str,
) -> ArenaSynthesisRevision | None:
    from sqlmodel import select

    result = await session.execute(
        select(Message).where(
            Message.debate_id == debate_id,
            Message.response_id == synthesis_id,
            Message.role == "arena_synthesis_revision",
        )
    )
    message = result.scalars().first()
    return _message_to_synthesis_revision(message) if message else None


async def _load_latest_synthesis_revision(
    session,
    debate_id: str,
    *,
    run_attempt: int,
    revision: int,
    status: str,
) -> ArenaSynthesisRevision | None:
    """Load the latest durable revision, including legacy fixed-ID rows."""
    from sqlmodel import select

    result = await session.execute(
        select(Message)
        .where(
            Message.debate_id == debate_id,
            Message.role == "arena_synthesis_revision",
        )
        .order_by(Message.created_at.desc())
    )
    for message in result.scalars().all():
        meta = message.meta or {}
        if (
            int(meta.get("run_attempt", 1) or 1) == run_attempt
            and int(meta.get("revision", 0) or 0) == revision
            and str(meta.get("status") or "provisional") == status
        ):
            return _message_to_synthesis_revision(message)
    return None


def _assert_revision_identity_matches(
    existing: ArenaSynthesisRevision,
    requested: ArenaSynthesisRevision,
) -> None:
    """Fail closed if one durable ID is reused for a different snapshot."""
    if (
        existing.input_hash != requested.input_hash
        or existing.revision != requested.revision
        or existing.status != requested.status
        or existing.response_ids != requested.response_ids
    ):
        from orchestration.checkpoints import CheckpointIntegrityError

        raise CheckpointIntegrityError(
            "Arena synthesis revision identity collision for " f"{requested.synthesis_id}"
        )


def _assert_final_revision_snapshot_matches(
    existing: ArenaSynthesisRevision,
    *,
    synthesis_id: str,
    input_hash: str,
    response_ids: tuple[str, ...],
) -> None:
    """Validate a takeover-reused final revision before skipping its provider call."""
    if (
        existing.synthesis_id != synthesis_id
        or existing.input_hash != input_hash
        or existing.response_ids != response_ids
        or existing.revision != 1
        or existing.status not in {"final", "failed"}
    ):
        from orchestration.checkpoints import CheckpointIntegrityError

        raise CheckpointIntegrityError(
            "Arena final synthesis revision does not match the terminal response snapshot"
        )


async def _persist_synthesis_revision(
    *,
    debate_id: str,
    run_attempt: int,
    revision: ArenaSynthesisRevision,
    backend,
    owner_id: str | None,
    lease_epoch: int | None,
) -> ArenaSynthesisRevision:
    """Persist a revision before publishing its terminal lifecycle event."""
    from models import DebateAttempt
    from orchestration.fencing import assert_execution_ownership
    from sqlalchemy.exc import IntegrityError
    from sqlmodel import select

    async with async_session_scope() as session:
        write_lease = _lease_for_arena_write(debate_id, run_attempt, owner_id, lease_epoch)
        if write_lease is not None:
            await assert_execution_ownership(session, write_lease)

        existing = await _load_synthesis_revision(session, debate_id, revision.synthesis_id)
        if existing is not None:
            _assert_revision_identity_matches(existing, revision)
            persisted = existing
        else:
            attempt_result = await session.execute(
                select(DebateAttempt.id).where(
                    DebateAttempt.debate_id == debate_id,
                    DebateAttempt.attempt_number == run_attempt,
                )
            )
            session.add(
                Message(
                    debate_id=debate_id,
                    attempt_id=attempt_result.scalar_one_or_none(),
                    response_id=revision.synthesis_id,
                    round_index=2,
                    role="arena_synthesis_revision",
                    persona="Synthesizer",
                    content=revision.content,
                    meta={
                        "mode": "arena",
                        "phase": "synthesis",
                        "contract_version": 1,
                        "synthesis_id": revision.synthesis_id,
                        "run_attempt": run_attempt,
                        "revision": revision.revision,
                        "status": revision.status,
                        "input_hash": revision.input_hash,
                        "response_ids": list(revision.response_ids),
                        "successful_count": revision.successful_count,
                        "total_count": revision.total_count,
                        "synthesis_report": revision.report,
                        "usage_call": _usage_call_to_meta(revision.usage_call),
                    },
                )
            )
            try:
                await session.commit()
                persisted = revision
            except IntegrityError as exc:
                await session.rollback()
                if not _is_response_identity_conflict(exc):
                    raise
                existing = await _load_synthesis_revision(session, debate_id, revision.synthesis_id)
                if existing is None:
                    raise
                _assert_revision_identity_matches(existing, revision)
                persisted = existing

    rev_verification_status = "unavailable"
    if isinstance(persisted.report, dict):
        rev_qm = persisted.report.get("quality_meta") or {}
        rev_verification_status = rev_qm.get("verification_status", "unavailable")
    await _publish_lifecycle_best_effort(
        backend,
        f"debate:{debate_id}",
        {
            "type": "arena_synthesis_revision",
            "contract_version": 1,
            "debate_id": str(debate_id),
            "synthesis_id": persisted.synthesis_id,
            "run_attempt": run_attempt,
            "revision": persisted.revision,
            "status": persisted.status,
            "content": persisted.content,
            "report": persisted.report,
            "input_hash": persisted.input_hash,
            "response_ids": list(persisted.response_ids),
            "successful_count": persisted.successful_count,
            "total_count": persisted.total_count,
            "verification_status": rev_verification_status,
            "is_verified": rev_verification_status == "verified",
            "pipeline_type": "structured",
            "report_version": 1,
        },
    )
    return persisted


async def persist_and_publish_arena_response(
    session,
    backend,
    debate_id: str,
    response: ArenaModelResponse,
    *,
    owner_id: str | None = None,
    lease_epoch: int | None = None,
) -> bool:
    """Persist arena response with statement-level fencing + DB unique identity.

    1. Lock/verify Debate ownership (lease_expires_at + owner + epoch) in-tx
    2. INSERT Message with response_id; unique constraint makes concurrent
       duplicates fail closed (IntegrityError → treated as already-exists)
    3. Commit; post-commit SSE is best-effort and never aborts fan-out

    Returns True if newly inserted, False if duplicate response_id.
    Raises ExecutionSupersededError if lease is no longer owned.
    """
    from datetime import datetime, timezone

    from orchestration.execution_context import get_current_execution_lease
    from orchestration.execution_lease import ExecutionSupersededError
    from sqlalchemy import select as sa_select
    from sqlalchemy.exc import IntegrityError

    lease = get_current_execution_lease()
    if owner_id is None and lease is not None:
        owner_id = lease.owner_id
    if lease_epoch is None and lease is not None:
        lease_epoch = lease.lease_epoch

    response_id = response.response_id
    if not response_id:
        raise ValueError("Arena response requires a durable response_id")

    now = datetime.now(timezone.utc)

    # --- Ownership gate: row-lock Debate so lease takeover cannot race INSERT ---
    if owner_id and lease_epoch is not None:
        ownership = await session.execute(
            sa_select(Debate.id)
            .where(Debate.id == debate_id)
            .where(Debate.runner_id == owner_id)
            .where(Debate.lease_epoch == lease_epoch)
            .where(Debate.status == "running")
            .where(Debate.lease_expires_at.is_not(None))
            .where(Debate.lease_expires_at > now)
            .with_for_update()
        )
        if ownership.first() is None:
            logger.warning(
                "arena_response.fenced_rejected debate_id=%s owner=%s epoch=%s",
                debate_id,
                owner_id,
                lease_epoch,
            )
            if lease:
                lease.lease_lost_event.set()
            raise ExecutionSupersededError(
                f"Arena response persist rejected: {debate_id} no longer owned by "
                f"{owner_id} at epoch {lease_epoch}"
            )

    # Fast path: already durable under this response_id
    existing = await session.execute(
        sa_select(Message.id)
        .where(
            Message.debate_id == debate_id,
            Message.response_id == response_id,
        )
        .limit(1)
    )
    if existing.first() is not None:
        return False

    msg = Message(
        debate_id=debate_id,
        response_id=response_id,
        round_index=1,
        role="arena_response",
        persona=response.display_name,
        content=response.content,
        meta={
            "model_id": response.model_id,
            "display_name": response.display_name,
            "provider": response.provider,
            "mode": "arena",
            "response_id": response.response_id,
            "run_attempt": response.run_attempt,
            "retry_generation": response.retry_generation,
            "logo_url": response.logo_url,
            "persona_type": response.persona_type,
            "persona_tagline": response.persona_tagline,
            "success": response.success,
            "error": response.error or (None if response.success else "Model failed to respond"),
            "error_code": response.error_code,
            "usage_call": _usage_call_to_meta(response.usage_call),
        },
        created_at=now,
    )
    session.add(msg)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if not _is_response_identity_conflict(exc):
            raise
        # Concurrent insert of same (debate_id, response_id) — durable duplicate
        return False

    # Post-commit SSE is best-effort — never abort model fan-out
    try:
        await _publish_lifecycle_best_effort(
            backend,
            f"debate:{debate_id}",
            {
                "type": "arena_response",
                "debate_id": str(debate_id),
                "model_id": response.model_id,
                "response_id": response.response_id,
                "display_name": response.display_name,
                "provider": response.provider,
                "content": response.content,
                "logo_url": response.logo_url,
                "persona_type": response.persona_type,
                "persona_tagline": response.persona_tagline,
                "success": response.success,
                "error": response.error
                or (None if response.success else "Model failed to respond"),
                "error_code": response.error_code,
                "run_attempt": response.run_attempt,
                "retry_generation": response.retry_generation,
            },
        )
    except Exception:
        logger.warning(
            "arena_response.sse_publish_failed debate_id=%s response_id=%s",
            debate_id,
            response_id,
            exc_info=True,
        )
    return True


async def _generate_and_persist_streamed_synthesis_revision(
    *,
    debate_id: str,
    run_attempt: int,
    prompt: str,
    responses: list[ArenaModelResponse],
    total_count: int,
    model_order: dict[str, int],
    backend,
    user_id: str | None,
    model_id: str | None,
    locale: str | None,
    owner_id: str | None,
    lease_epoch: int | None,
    revision_number: int,
    revision_status: str,
    visibility_started_at: float | None = None,
) -> ArenaSynthesisRevision:
    """Stream and durably identify one synthesis response snapshot."""
    from model_gateway import route_llm_stream
    from parliament.model_registry import get_default_model

    from arena.delta_publisher import ArenaDeltaPublisher
    from config import settings

    ordered = sorted(
        (response for response in responses if response.success),
        key=lambda response: model_order.get(response.model_id, 999),
    )
    response_ids = _response_snapshot(ordered, model_order=model_order)
    input_hash = _synthesis_snapshot_hash(prompt, ordered, model_order=model_order)
    synthesis_id = _synthesis_revision_id(
        debate_id,
        run_attempt,
        revision_number,
        input_hash,
    )
    synthesis_model = resolve_model_info(model_id) if model_id else None
    synthesis_model = synthesis_model or get_default_model()

    await _publish_lifecycle_best_effort(
        backend,
        f"debate:{debate_id}",
        {
            "type": "arena_synthesis_started",
            "contract_version": 1,
            "debate_id": str(debate_id),
            "synthesis_id": synthesis_id,
            "run_attempt": run_attempt,
            "revision": revision_number,
            "status": revision_status,
            "input_hash": input_hash,
            "response_ids": list(response_ids),
            "successful_count": len(ordered),
            "total_count": total_count,
            "pipeline_type": "structured",
            "report_version": 1,
        },
    )

    source_text = "\n\n".join(
        f"### {response.display_name} ({response.provider})\n{response.content}"
        for response in ordered
    )
    language_instruction = (
        f" Write the synthesis in the '{locale}' language." if locale and locale != "en" else ""
    )
    if revision_status == "provisional":
        system_content = (
            "Create a concise provisional decision synthesis from the available "
            "model responses. State the current recommendation, strongest evidence, "
            "material disagreements, risks, and next actions. Do not claim that all "
            "models have responded. Use clear Markdown."
        )
        response_label = "Available responses"
        max_tokens = int(getattr(settings, "ARENA_PROVISIONAL_MAX_TOKENS", 600))
    else:
        system_content = (
            "Create the definitive decision synthesis from all successful model "
            "responses. State the recommendation, strongest evidence, material "
            "disagreements, risks, confidence, and concrete next actions. "
            "Use clear Markdown."
        )
        response_label = "Successful responses"
        max_tokens = int(getattr(settings, "SYNTHESIS_MAX_TOKENS", 2000))
    messages = [
        {
            "role": "system",
            "content": system_content + language_instruction,
        },
        {
            "role": "user",
            "content": (
                f"Question:\n{prompt}\n\n"
                f"{response_label} ({len(ordered)}/{total_count}):\n{source_text}"
            ),
        },
    ]

    async def _publish_delta(event: dict) -> None:
        await backend.publish(f"debate:{debate_id}", event)

    delta_publisher = ArenaDeltaPublisher(
        publish_fn=_publish_delta,
        response_id=synthesis_id,
        model_id="synthesizer",
        flush_interval_ms=int(getattr(settings, "ARENA_DELTA_FLUSH_MS", 150) or 30),
        event_type="arena_synthesis_delta",
        extra_payload={
            "contract_version": 1,
            "debate_id": str(debate_id),
            "synthesis_id": synthesis_id,
            "run_attempt": run_attempt,
            "revision": revision_number,
            "status": revision_status,
            "input_hash": input_hash,
            "response_ids": list(response_ids),
            "successful_count": len(ordered),
            "total_count": total_count,
        },
    )
    await delta_publisher.start()
    first_visible_recorded = False

    def _record_first_visible() -> None:
        nonlocal first_visible_recorded
        if first_visible_recorded or visibility_started_at is None:
            return
        first_visible_recorded = True
        try:
            from observability.metrics import (
                record_arena_quorum_to_first_synthesis,
            )

            record_arena_quorum_to_first_synthesis(
                (time.monotonic() - visibility_started_at) * 1000
            )
        except Exception:
            logger.debug(
                "arena provisional synthesis metric failed",
                exc_info=True,
            )

    async def _on_delta(delta) -> None:
        await delta_publisher.push(delta)
        _record_first_visible()

    try:
        result = await asyncio.wait_for(
            route_llm_stream(
                messages=messages,
                model_id=synthesis_model.litellm_model,
                temperature=0.2,
                max_tokens=max_tokens,
                on_delta=_on_delta,
                debate_id=debate_id,
                user_id=user_id,
            ),
            timeout=float(getattr(settings, "ARENA_SYNTHESIS_TIMEOUT_SECONDS", 90)),
        )
    finally:
        await delta_publisher.flush()
        await delta_publisher.close()

    usage_call = _usage_call_from_gateway_result(result)
    persisted_status = revision_status
    if result.success and result.content.strip():
        content = result.content
        report = _build_synthesis_report_nonfatal(
            prompt=prompt,
            content=content,
            model_responses=[
                {
                    "model_id": response.model_id,
                    "display_name": response.display_name,
                    "provider": response.provider,
                    "content": response.content,
                    "success": response.success,
                }
                for response in ordered
            ],
            debate_id=debate_id,
            synthesis_id=synthesis_id,
        )
    elif revision_status == "provisional":
        raise RuntimeError(result.error_message or "Provisional synthesis returned no content.")
    else:
        persisted_status = "failed"
        top_response = ordered[0]
        content = (
            "⚠️ Final synthesis unavailable. Source responses remain available.\n\n"
            f"**{top_response.display_name}:**\n{top_response.content}"
        )
        report = None

    revision = ArenaSynthesisRevision(
        synthesis_id=synthesis_id,
        content=content,
        report=report,
        response_ids=response_ids,
        successful_count=len(ordered),
        total_count=total_count,
        input_hash=input_hash,
        revision=revision_number,
        status=persisted_status,
        usage_call=usage_call,
    )
    persisted = await _persist_synthesis_revision(
        debate_id=debate_id,
        run_attempt=run_attempt,
        revision=revision,
        backend=backend,
        owner_id=owner_id,
        lease_epoch=lease_epoch,
    )
    _record_first_visible()
    return persisted


async def _generate_and_persist_provisional_synthesis(
    *,
    debate_id: str,
    run_attempt: int,
    prompt: str,
    responses: list[ArenaModelResponse],
    total_count: int,
    model_order: dict[str, int],
    backend,
    user_id: str | None,
    model_id: str | None,
    locale: str | None,
    owner_id: str | None,
    lease_epoch: int | None,
    quorum_reached_at: float,
) -> ArenaSynthesisRevision:
    return await _generate_and_persist_streamed_synthesis_revision(
        debate_id=debate_id,
        run_attempt=run_attempt,
        prompt=prompt,
        responses=responses,
        total_count=total_count,
        model_order=model_order,
        backend=backend,
        user_id=user_id,
        model_id=model_id,
        locale=locale,
        owner_id=owner_id,
        lease_epoch=lease_epoch,
        revision_number=0,
        revision_status="provisional",
        visibility_started_at=quorum_reached_at,
    )


async def _generate_and_persist_final_synthesis(
    *,
    debate_id: str,
    run_attempt: int,
    prompt: str,
    responses: list[ArenaModelResponse],
    total_count: int,
    model_order: dict[str, int],
    backend,
    user_id: str | None,
    model_id: str | None,
    locale: str | None,
    owner_id: str | None,
    lease_epoch: int | None,
) -> ArenaSynthesisRevision:
    return await _generate_and_persist_streamed_synthesis_revision(
        debate_id=debate_id,
        run_attempt=run_attempt,
        prompt=prompt,
        responses=responses,
        total_count=total_count,
        model_order=model_order,
        backend=backend,
        user_id=user_id,
        model_id=model_id,
        locale=locale,
        owner_id=owner_id,
        lease_epoch=lease_epoch,
        revision_number=1,
        revision_status="final",
    )


@dataclass
class ArenaResult:
    """Result of an arena run."""

    final_answer: str
    final_meta: dict
    usage_tracker: UsageAccumulator
    status: str
    error_reason: str | None = None
    model_responses: List[ArenaModelResponse] = field(default_factory=list)


async def run_arena(
    debate_id: str,
    *,
    model_id: str | None = None,
    continue_pipeline: bool = False,
    execution_owner_id: str | None = None,
    lease_epoch: int | None = None,
) -> ArenaResult:
    """
    Orchestrate an Arena mode run:
    1. Fan-out to all SOTA models in parallel
    2. Stream each response as it arrives
    3. Synthesize a final verdict from all responses
    """
    from sqlmodel import select

    from config import settings

    # Load debate data
    async with async_session_scope() as session:
        debate = await session.get(Debate, debate_id)
        if not debate:
            raise ValueError(f"Debate {debate_id} not found")
        prompt = debate.prompt
        config = debate.config or {}
        panel_config = debate.panel_config
        user_id = debate.user_id
        locale = config.get("locale")
        run_attempt = debate.run_attempt or 1

    # The stored panel is the execution contract. Only legacy runs without a
    # non-empty panel retain the historical global Arena fallback.
    arena_models = _select_arena_execution_models(panel_config)
    if not arena_models:
        raise ValueError("No arena models available. Configure at least one provider API key.")

    backend = get_sse_backend()
    usage = UsageAccumulator()
    model_order = {model.id: index for index, model in enumerate(arena_models)}
    min_required = int(
        getattr(
            settings,
            "MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS",
            MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS,
        )
    )
    progressive_enabled = getattr(
        settings, "ARENA_PROGRESSIVE_SYNTHESIS_ENABLED", False
    ) is True and not (settings.STAGED_DECISION_PIPELINE and not continue_pipeline)
    provisional_revision: ArenaSynthesisRevision | None = None
    all_models_terminal_at: float | None = None

    # Load responses with checkpoint safety
    perspectives_input = {
        "prompt": prompt,
        "models": [m.id for m in arena_models],
        "run_attempt": run_attempt,
    }

    async def load_perspectives_fn(session):
        stmt = (
            select(Message)
            .where(Message.debate_id == debate_id)
            .where(Message.role == "arena_response")
        )
        result = await session.execute(stmt)
        return _canonical_attempt_responses(
            list(result.scalars().all()),
            run_attempt=run_attempt,
            allowed_model_ids=set(model_order),
        )

    async def run_perspectives_fn():
        nonlocal provisional_revision, all_models_terminal_at

        if progressive_enabled:
            async with async_session_scope() as session:
                provisional_revision = await _load_latest_synthesis_revision(
                    session,
                    debate_id,
                    run_attempt=run_attempt,
                    revision=0,
                    status="provisional",
                )

        # Notify start
        await _publish_lifecycle_best_effort(
            backend,
            f"debate:{debate_id}",
            {
                "type": "arena_started",
                "contract_version": 1,
                "debate_id": str(debate_id),
                "models": [
                    {
                        "model_id": m.id,
                        "display_name": m.display_name,
                        "provider": m.provider,
                        "logo_url": m.logo_url,
                        "persona_type": m.persona_type,
                        "persona_tagline": m.persona_tagline,
                    }
                    for m in arena_models
                ],
            },
        )

        # Build locale instruction if set
        _locale_instruction = ""
        if locale and locale != "en":
            _locale_instruction = f"\nIMPORTANT: Respond in the '{locale}' language.\n"

        async def _call_model(
            model_info, response_id: str, deadline: float, timing: dict | None = None, lifecycle_payload: dict | None = None
        ):
            """Call a single SOTA model and return its response.

            Uses streaming when available: publishes model_response_delta events
            via SSE as tokens arrive, then persists the final response.
            """
            if timing is not None:
                timing["start_ts"] = time.monotonic()
            from config import settings as _settings

            stream_enabled = getattr(_settings, "STREAMING_RESPONSES_ENABLED", True)
            timeout_seconds = getattr(_settings, "ARENA_MODEL_TIMEOUT_SECONDS", 45)

            def remaining_timeout() -> float:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise asyncio.TimeoutError
                return min(float(timeout_seconds), remaining)

            system_prompt = get_compiled_model_prompt(
                model_display_name=model_info.display_name,
                provider_name=model_info.provider.capitalize(),
                locale=locale,
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            if stream_enabled:
                # Streaming path: ArenaDeltaPublisher (first immediate, rest coalesced)
                from arena.delta_publisher import ArenaDeltaPublisher
                from config import settings as _cfg

                channel = f"debate:{debate_id}"

                async def _publish_delta_event(event: dict) -> None:
                    event.setdefault("display_name", model_info.display_name)
                    event.setdefault("run_attempt", run_attempt)
                    event.setdefault("retry_generation", 0)
                    await backend.publish(channel, event)

                delta_pub = ArenaDeltaPublisher(
                    publish_fn=_publish_delta_event,
                    response_id=response_id,
                    model_id=model_info.id,
                    flush_interval_ms=int(getattr(_cfg, "ARENA_DELTA_FLUSH_MS", 30) or 30),
                )
                await delta_pub.start()

                _started_emitted = False
                _lifecycle = lifecycle_payload or {}

                async def on_delta(delta):
                    nonlocal _started_emitted
                    if timing is not None and timing.get("first_delta_ts") is None:
                        timing["first_delta_ts"] = time.monotonic()
                    if timing is not None:
                        timing["delta_count"] = timing.get("delta_count", 0) + 1
                    if not _started_emitted:
                        _started_emitted = True
                        if timing is not None:
                            timing["lifecycle_started"] = True
                        await _publish_lifecycle_best_effort(
                            backend,
                            f"debate:{debate_id}",
                            {"type": "model_response_started", **_lifecycle},
                        )
                    await delta_pub.push(delta)

                try:
                    from model_gateway import route_llm_stream

                    arena_max = getattr(_settings, "ARENA_MAX_TOKENS", 1200)

                    # A3: Per-model timeout for streaming path
                    try:
                        result = await asyncio.wait_for(
                            route_llm_stream(
                                messages=messages,
                                model_id=model_info.litellm_model or model_info.id,
                                temperature=0.7,
                                max_tokens=arena_max,
                                on_delta=on_delta,
                                debate_id=debate_id,
                                user_id=user_id,
                            ),
                            timeout=remaining_timeout(),
                        )
                    except asyncio.TimeoutError:
                        raise RuntimeError(
                            f"Model {model_info.display_name} timed out after {timeout_seconds} seconds."
                        ) from None
                    finally:
                        # Flush pending tokens before lifecycle boundary
                        await delta_pub.flush()
                        await delta_pub.close()

                    if result.success:
                        call_usage = _usage_call_from_gateway_result(result)
                        return ArenaModelResponse(
                            model_id=model_info.id,
                            display_name=model_info.display_name,
                            provider=model_info.provider,
                            content=result.content,
                            success=True,
                            logo_url=model_info.logo_url,
                            persona_type=model_info.persona_type,
                            persona_tagline=model_info.persona_tagline,
                            usage_call=call_usage,
                        ), call_usage
                    else:
                        non_retryable_stream_errors = {
                            "invalid_credentials",
                            "insufficient_balance",
                            "model_key_unresolved",
                            "unknown_model",
                        }
                        if result.error_code in non_retryable_stream_errors:
                            return ArenaModelResponse(
                                model_id=model_info.id,
                                display_name=model_info.display_name,
                                provider=model_info.provider,
                                content=f"⚠️ This model failed to respond: {result.error_message}",
                                success=False,
                                logo_url=model_info.logo_url,
                                persona_type=model_info.persona_type,
                                persona_tagline=model_info.persona_tagline,
                                error=result.error_message,
                                error_code=result.error_code,
                            ), None

                        # Transient streaming failures may use the non-streaming
                        # route once within the same total deadline.
                        logger.warning(
                            f"Streaming failed for {model_info.display_name}: "
                            f"{result.error_message}. Attempting non-streaming fallback."
                        )
                        try:
                            arena_max_fb = getattr(_settings, "ARENA_MAX_TOKENS", 1200)
                            fallback_content, fallback_usage = await asyncio.wait_for(
                                call_llm_for_role(
                                    messages,
                                    role=f"Arena:{model_info.display_name}",
                                    temperature=0.7,
                                    max_tokens=arena_max_fb,
                                    model_override=model_info.litellm_model,
                                    debate_id=debate_id,
                                    extra_tags={"mode": "arena", "arena_model": model_info.id},
                                ),
                                timeout=remaining_timeout(),
                            )
                            return ArenaModelResponse(
                                model_id=model_info.id,
                                display_name=model_info.display_name,
                                provider=model_info.provider,
                                content=fallback_content,
                                success=True,
                                logo_url=model_info.logo_url,
                                persona_type=model_info.persona_type,
                                persona_tagline=model_info.persona_tagline,
                            ), fallback_usage
                        except Exception as fb_exc:
                            logger.warning(
                                f"Non-streaming fallback also failed for "
                                f"{model_info.display_name}: {fb_exc}"
                            )
                            # Convert to failed ArenaModelResponse — do NOT raise
                            err_msg = result.error_message or str(fb_exc)
                            err_code = result.error_code or "stream_and_fallback_failed"
                            from llm_errors import classify_provider_exception

                            failure = classify_provider_exception(fb_exc)
                            return ArenaModelResponse(
                                model_id=model_info.id,
                                display_name=model_info.display_name,
                                provider=model_info.provider,
                                content=f"⚠️ This model failed to respond: {failure.message}",
                                success=False,
                                logo_url=model_info.logo_url,
                                persona_type=model_info.persona_type,
                                persona_tagline=model_info.persona_tagline,
                                error=err_msg,
                                error_code=failure.code.value,
                            ), None
                except Exception:
                    raise

            # Non-streaming fallback
            try:
                arena_max = getattr(settings, "ARENA_MAX_TOKENS", 1200)

                # A4: Per-model timeout for non-streaming path
                try:
                    content, call_usage = await asyncio.wait_for(
                        call_llm_for_role(
                            messages,
                            role=f"Arena:{model_info.display_name}",
                            temperature=0.7,
                            max_tokens=arena_max,
                            model_override=model_info.litellm_model,
                            debate_id=debate_id,
                            extra_tags={"mode": "arena", "arena_model": model_info.id},
                        ),
                        timeout=remaining_timeout(),
                    )
                except asyncio.TimeoutError:
                    raise RuntimeError(
                        f"Model {model_info.display_name} timed out after {timeout_seconds} seconds."
                    ) from None

                return ArenaModelResponse(
                    model_id=model_info.id,
                    display_name=model_info.display_name,
                    provider=model_info.provider,
                    content=content,
                    success=True,
                    logo_url=model_info.logo_url,
                    persona_type=model_info.persona_type,
                    persona_tagline=model_info.persona_tagline,
                ), call_usage
            except Exception as e:
                logger.error(f"Arena model {model_info.id} failed: {e}")

                from llm_errors import ProviderFailureCode, classify_provider_exception

                failure = classify_provider_exception(e)
                err_code = failure.code.value
                friendly_message = failure.message

                if err_code == ProviderFailureCode.INVALID_CREDENTIALS.value:
                    friendly_message = (
                        "⚠️ This model provider configuration is invalid (invalid credentials)."
                    )
                elif err_code == ProviderFailureCode.INSUFFICIENT_BALANCE.value:
                    friendly_message = "⚠️ This model provider has run out of credits."
                elif err_code == ProviderFailureCode.RATE_LIMIT_EXCEEDED.value:
                    friendly_message = "⚠️ Rate limit exceeded for this model provider. Please try again in 1 minute."
                elif err_code == ProviderFailureCode.MODEL_TIMEOUT.value:
                    friendly_message = "⚠️ The model provider request timed out."
                elif err_code == ProviderFailureCode.API_ERROR.value:
                    friendly_message = "⚠️ The model provider API returned an error."
                else:
                    friendly_message = f"⚠️ This model failed to respond: {failure.message}"

                return ArenaModelResponse(
                    model_id=model_info.id,
                    display_name=model_info.display_name,
                    provider=model_info.provider,
                    content=friendly_message,
                    success=False,
                    logo_url=model_info.logo_url,
                    persona_type=model_info.persona_type,
                    persona_tagline=model_info.persona_tagline,
                    error=str(e),
                    error_code=err_code,
                ), None

        # A5: Persist/publish each model response as it completes (not after all finish).
        # Uses asyncio.as_completed so fast models become visible immediately.
        async def _call_and_persist(model_info):
            """Call a model and persist/publish its response immediately.

            Contract: this function NEVER raises. Provider/model errors are
            converted into ArenaModelResponse(success=False) and persisted.
            """
            _timing: dict = {}
            retry_generation = 0
            response_id = (
                f"resp-{debate_id}-" f"a{run_attempt}-" f"g{retry_generation}-" f"{model_info.id}"
            )
            lifecycle_payload = {
                "contract_version": 1,
                "response_id": response_id,
                "model_id": model_info.id,
                "display_name": model_info.display_name,
                "provider": model_info.provider,
                "run_attempt": run_attempt,
                "retry_generation": retry_generation,
            }
            from config import settings as _settings

            total_timeout = float(getattr(_settings, "ARENA_MODEL_TOTAL_TIMEOUT_S", 60))
            deadline = asyncio.get_running_loop().time() + total_timeout
            for event_type in (
                "model_response_queued",
                "model_response_connecting",
            ):
                await _publish_lifecycle_best_effort(
                    backend,
                    f"debate:{debate_id}",
                    {"type": event_type, **lifecycle_payload},
                )

            try:
                async with asyncio.timeout_at(deadline):
                    result = await _call_model(model_info, response_id, deadline, _timing, lifecycle_payload)
                response, call_usage = result
            except Exception as exc:
                logger.error(f"Arena model task exception for {model_info.id}: {exc}")

                from llm_errors import ProviderFailureCode, classify_provider_exception

                failure = classify_provider_exception(exc)
                err_code = failure.code.value
                friendly_message = failure.message

                if err_code == ProviderFailureCode.INVALID_CREDENTIALS.value:
                    friendly_message = (
                        "⚠️ This model provider configuration is invalid (invalid credentials)."
                    )
                elif err_code == ProviderFailureCode.INSUFFICIENT_BALANCE.value:
                    friendly_message = "⚠️ This model provider has run out of credits."
                elif err_code == ProviderFailureCode.RATE_LIMIT_EXCEEDED.value:
                    friendly_message = "⚠️ Rate limit exceeded for this model provider. Please try again in 1 minute."
                elif err_code == ProviderFailureCode.MODEL_TIMEOUT.value:
                    friendly_message = "⚠️ The model provider request timed out."
                elif err_code == ProviderFailureCode.API_ERROR.value:
                    friendly_message = "⚠️ The model provider API returned an error."
                else:
                    friendly_message = f"⚠️ This model encountered an error: {failure.message}"

                response = ArenaModelResponse(
                    model_id=model_info.id,
                    display_name=model_info.display_name,
                    provider=model_info.provider,
                    content=friendly_message,
                    success=False,
                    logo_url=model_info.logo_url,
                    persona_type=model_info.persona_type,
                    persona_tagline=model_info.persona_tagline,
                    error=str(exc),
                    error_code=err_code,
                )
                call_usage = None

            # Non-streaming calls and failures without visible deltas still
            # enter the same monotonic lifecycle as streaming responses.
            if not _timing.get("lifecycle_started"):
                await _publish_lifecycle_best_effort(
                    backend,
                    f"debate:{debate_id}",
                    {"type": "model_response_started", **lifecycle_payload},
                )
                _timing["lifecycle_started"] = True

            response.response_id = response_id
            response.run_attempt = run_attempt
            response.retry_generation = retry_generation
            response.usage_call = call_usage
            if not response.success:
                from llm_errors import classify_provider_exception

                response.error = classify_provider_exception(
                    RuntimeError(response.error or "Model failed to respond")
                ).message

            await _publish_lifecycle_best_effort(
                backend,
                f"debate:{debate_id}",
                {"type": "model_response_persisting", **lifecycle_payload},
            )

            # Persist before the terminal lifecycle event. A completed event
            # therefore guarantees that the canonical response can be fetched.
            try:
                async with async_session_scope() as session:
                    await persist_and_publish_arena_response(
                        session,
                        backend,
                        debate_id,
                        response,
                        owner_id=execution_owner_id,
                        lease_epoch=lease_epoch,
                    )
            except Exception as persist_exc:
                # P2 #10: Even persistence failures must not escape — the parent
                # loop should see every model task complete normally.
                from orchestration.execution_lease import ExecutionSupersededError

                if isinstance(persist_exc, ExecutionSupersededError):
                    raise
                logger.error(
                    "Arena response persistence failed for %s: %s",
                    model_info.id,
                    persist_exc,
                    exc_info=True,
                )
                # Publish a storage failure event so the frontend doesn't hang.
                await _publish_lifecycle_best_effort(
                    backend,
                    f"debate:{debate_id}",
                    {
                        "type": "model_response_storage_failed",
                        **lifecycle_payload,
                        "error": "Response generated but could not be stored.",
                        "error_code": "persistence_failed",
                    },
                )
                # Return a failed response as well as publishing the terminal
                # event.  The original provider response may be successful,
                # but content that was not durably persisted must never enter
                # synthesis or be reported as a successful model result.
                failed_response = replace(
                    response,
                    success=False,
                    content="Response could not be stored. Please retry this model.",
                    error="Response persistence failed.",
                    error_code="persistence_failed",
                )
                terminal_payload = {
                    "type": "model_response_failed",
                    **lifecycle_payload,
                    "error": "Response persistence failed.",
                    "error_code": "persistence_failed",
                }
                await _publish_lifecycle_best_effort(
                    backend, f"debate:{debate_id}", terminal_payload
                )
                return failed_response, call_usage

            terminal_payload = {
                "type": "model_response_completed" if response.success else "model_response_failed",
                **lifecycle_payload,
                # Carry terminal content so a reconnect that missed earlier
                # deltas can still render the successful answer immediately.
                "content": response.content if response.success else "",
            }
            if not response.success:
                terminal_payload.update(
                    {
                        "error": (response.error or "Model failed to respond")[:200],
                        "error_code": response.error_code,
                    }
                )
            # Only emit terminal event if response was actually persisted (or already existed)
            # to prevent frontend from seeing "completed" for a response that isn't in DB.
            # persisted=False means duplicate already in DB — still safe to emit terminal.
            await _publish_lifecycle_best_effort(backend, f"debate:{debate_id}", terminal_payload)

            if PROMETHEUS_AVAILABLE and _timing.get("start_ts"):
                _provider = model_info.provider
                _family = _derive_model_family(model_info)
                _now = time.monotonic()
                _total_sec = _now - _timing["start_ts"]
                record_model_latency(_provider, _family, response.success, _total_sec)
                _first = _timing.get("first_delta_ts")
                if _first:
                    _ttft_sec = _first - _timing["start_ts"]
                    record_ttft(_provider, _family, _ttft_sec)
                    record_connect_latency(_provider, _family, _ttft_sec)
                    _stream_dur = _now - _first
                    _dps = _timing.get("delta_count", 0) / _stream_dur if _stream_dur > 0 else 0
                    record_stream_duration(
                        _provider, "success" if response.success else "failure", _stream_dur
                    )
                    record_stream_dps(_provider, _dps)

            return response, call_usage

        # Reuse rows already persisted for this attempt before a worker
        # takeover. This prevents completed provider calls from being repeated
        # merely because the aggregate perspectives checkpoint was incomplete.
        async with async_session_scope() as session:
            responses = await load_perspectives_fn(session)
        completed_models = {response.model_id for response in responses}

        # Fan-out: call only missing models, collect as each completes.
        tasks: list[asyncio.Task] = []
        for model in arena_models:
            if model.id in completed_models:
                continue
            task = asyncio.create_task(_call_and_persist(model))
            tasks.append(task)
        provisional_task: asyncio.Task[ArenaSynthesisRevision | None] | None = None
        provisional_state: dict[str, object] = {
            "started": False,
            "response_ids": (),
        }
        quorum_reached_at: float | None = None

        async def _run_provisional_after_grace(
            reached_at: float,
        ) -> ArenaSynthesisRevision | None:
            grace_ms = int(getattr(settings, "ARENA_SYNTHESIS_GRACE_MS", 750))
            if grace_ms > 0:
                await asyncio.sleep(grace_ms / 1000)
            # If every model reached a terminal state during the grace period,
            # go directly to the final revision and avoid the extra call.
            if not any(not task.done() for task in tasks):
                return None

            snapshot = [replace(response) for response in responses if response.success]
            if len(snapshot) < min_required:
                return None
            provisional_state["started"] = True
            snapshot_ids = _response_snapshot(snapshot, model_order=model_order)
            provisional_state["response_ids"] = snapshot_ids
            snapshot_hash = _synthesis_snapshot_hash(prompt, snapshot, model_order=model_order)
            synthesis_id = _synthesis_revision_id(
                debate_id,
                run_attempt,
                0,
                snapshot_hash,
            )

            async def _load_revision(session):
                return await _load_synthesis_revision(session, debate_id, synthesis_id)

            async def _run_revision():
                try:
                    return await _generate_and_persist_provisional_synthesis(
                        debate_id=debate_id,
                        run_attempt=run_attempt,
                        prompt=prompt,
                        responses=snapshot,
                        total_count=len(arena_models),
                        model_order=model_order,
                        backend=backend,
                        user_id=user_id,
                        model_id=model_id,
                        locale=locale,
                        owner_id=execution_owner_id,
                        lease_epoch=lease_epoch,
                        quorum_reached_at=reached_at,
                    )
                except asyncio.CancelledError:
                    logger.info(
                        "arena.provisional_synthesis_superseded " "debate_id=%s input_hash=%s",
                        debate_id,
                        snapshot_hash,
                    )
                    return None

            return await run_with_checkpoint(
                debate_id,
                "arena_synthesis_provisional",
                {
                    "prompt": prompt,
                    "response_ids": list(snapshot_ids),
                    "input_hash": snapshot_hash,
                    "run_attempt": run_attempt,
                },
                _run_revision,
                _load_revision,
                owner_id=execution_owner_id,
                lease_epoch=lease_epoch,
                long_stage=True,
            )

        def _maybe_schedule_provisional() -> None:
            nonlocal provisional_task, quorum_reached_at
            if (
                not progressive_enabled
                or provisional_revision is not None
                or provisional_task is not None
            ):
                return
            successful_count = sum(1 for response in responses if response.success)
            if successful_count < min_required:
                return
            if not any(not task.done() for task in tasks):
                return
            quorum_reached_at = time.monotonic()
            provisional_task = asyncio.create_task(_run_provisional_after_grace(quorum_reached_at))

        _maybe_schedule_provisional()

        try:
            # Every model owns its real provider deadline. Reaching synthesis
            # quorum may start a provisional decision, but it must never mutate
            # a still-running model into a synthetic failure.
            for completed_task in asyncio.as_completed(tasks):
                try:
                    response, _call_usage = await completed_task
                except Exception as exc:
                    from orchestration.checkpoints import (
                        CheckpointIntegrityError,
                        CheckpointOwnershipLostError,
                    )
                    from orchestration.execution_lease import ExecutionSupersededError

                    if isinstance(
                        exc,
                        (
                            ExecutionSupersededError,
                            CheckpointOwnershipLostError,
                            CheckpointIntegrityError,
                        ),
                    ):
                        raise
                    logger.error(
                        "Arena model task failed outside provider boundary: %s",
                        exc,
                        exc_info=True,
                    )
                    continue

                responses.append(response)
                _maybe_schedule_provisional()

            all_models_terminal_at = time.monotonic()

            if provisional_task is not None:
                final_snapshot_ids = _response_snapshot(
                    responses,
                    model_order=model_order,
                )
                provisional_is_obsolete = (
                    bool(provisional_state["started"])
                    and provisional_state["response_ids"] != final_snapshot_ids
                )
                if not provisional_task.done() and (
                    not provisional_state["started"] or provisional_is_obsolete
                ):
                    provisional_task.cancel()
                try:
                    provisional_revision = await provisional_task
                except asyncio.CancelledError:
                    provisional_revision = None
                except Exception as exc:
                    from orchestration.checkpoints import (
                        CheckpointIntegrityError,
                        CheckpointOwnershipLostError,
                    )
                    from orchestration.execution_lease import ExecutionSupersededError

                    if isinstance(
                        exc,
                        (
                            ExecutionSupersededError,
                            CheckpointOwnershipLostError,
                            CheckpointIntegrityError,
                        ),
                    ):
                        raise
                    logger.warning(
                        "arena.provisional_synthesis_failed debate_id=%s error=%s",
                        debate_id,
                        exc,
                        exc_info=True,
                    )
                    provisional_revision = None
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if provisional_task is not None and not provisional_task.done():
                provisional_task.cancel()
                await asyncio.gather(provisional_task, return_exceptions=True)

        # Sort responses back to original arena_models order
        responses.sort(key=lambda r: model_order.get(r.model_id, 999))
        return responses

    from orchestration.checkpoints import run_with_checkpoint

    model_responses = await run_with_checkpoint(
        debate_id,
        "arena_perspectives",
        perspectives_input,
        run_perspectives_fn,
        load_perspectives_fn,
        owner_id=execution_owner_id,
        lease_epoch=lease_epoch,
    )
    for response in model_responses:
        if response.usage_call is not None:
            usage.add_call(response.usage_call)

    # Check if we have enough successful responses for synthesis
    successful = [r for r in model_responses if r.success]
    if len(successful) < min_required:
        # NOTE: no terminal event is published here. Terminal state has exactly
        # one owner — the orchestrator — which emits debate_failed only AFTER
        # the durable terminal DB commit. Emitting a terminal event from the
        # child engine would let SSE say "failed" while the DB still says
        # "running" (a release-blocker race, especially in Celery mode).
        return ArenaResult(
            final_answer="All models failed to respond. Please try again.",
            final_meta={
                "mode": "arena",
                "error": "all_models_failed",
                "models": [
                    {
                        "model_id": r.model_id,
                        "display_name": r.display_name,
                        "provider": r.provider,
                        "success": r.success,
                        "logo_url": r.logo_url,
                    }
                    for r in model_responses
                ],
                "successful_count": 0,
                "total_count": len(model_responses),
            },
            usage_tracker=usage,
            status="failed",
            error_reason="all_models_failed",
            model_responses=model_responses,
        )

    # Staged execution pause check
    if settings.STAGED_DECISION_PIPELINE and not continue_pipeline:
        # Update debate status to perspectives_ready in DB
        async with async_session_scope() as session:
            from orchestration.fencing import fenced_debate_update

            write_lease = _lease_for_arena_write(
                debate_id, run_attempt, execution_owner_id, lease_epoch
            )
            if write_lease is not None:
                await fenced_debate_update(
                    session,
                    write_lease,
                    {"status": "perspectives_ready"},
                    what="arena perspectives pause",
                )
            else:
                db_debate = await session.get(Debate, debate_id)
                db_debate.status = "perspectives_ready"
                session.add(db_debate)
            await session.commit()

        # Publish early pause event
        await _publish_lifecycle_best_effort(
            backend,
            f"debate:{debate_id}",
            {
                "type": "perspectives_ready",
                "debate_id": str(debate_id),
            },
        )
        return ArenaResult(
            final_answer="Perspectives collected. Synthesis paused.",
            final_meta={
                "mode": "arena",
                "models": [
                    {
                        "model_id": r.model_id,
                        "display_name": r.display_name,
                        "provider": r.provider,
                        "success": r.success,
                        "logo_url": r.logo_url,
                        "persona_type": r.persona_type,
                        "persona_tagline": r.persona_tagline,
                    }
                    for r in model_responses
                ],
                "successful_count": len(successful),
                "total_count": len(model_responses),
                "usage": usage.snapshot(),
            },
            usage_tracker=usage,
            status="perspectives_ready",
            model_responses=model_responses,
        )

    if provisional_revision is None:
        async with async_session_scope() as session:
            provisional_revision = await _load_latest_synthesis_revision(
                session,
                debate_id,
                run_attempt=run_attempt,
                revision=0,
                status="provisional",
            )
    if provisional_revision is not None and provisional_revision.usage_call is not None:
        usage.add_call(provisional_revision.usage_call)

    # Synthesize final verdict
    final_response_ids = _response_snapshot(successful, model_order=model_order)
    final_input_hash = _synthesis_snapshot_hash(prompt, successful, model_order=model_order)
    promote_provisional = (
        provisional_revision is not None
        and provisional_revision.status == "provisional"
        and provisional_revision.response_ids == final_response_ids
    )
    synthesis_input = {
        "prompt": prompt,
        "responses": [r.content for r in model_responses if r.success],
        "response_ids": list(final_response_ids),
        "input_hash": final_input_hash,
        "promote_provisional": promote_provisional,
    }

    async def load_synthesis_fn(session):
        stmt = (
            select(Message)
            .where(Message.debate_id == debate_id)
            .where(Message.role == "arena_synthesis")
            .where(Message.response_id == f"synth-{debate_id}-a{run_attempt}")
        )
        result = await session.execute(stmt)
        msg = result.scalars().first()
        if msg:
            sreport = msg.meta.get("synthesis_report") if msg.meta else None
            meta = {
                "synthesis_status": "succeeded"
                if msg.meta and msg.meta.get("synthesis_success")
                else "failed",
                "synthesis_error": msg.meta.get("synthesis_error") if msg.meta else None,
                "fallback_model": msg.meta.get("fallback_model") if msg.meta else None,
                "fallback_reason": msg.meta.get("fallback_reason") if msg.meta else None,
                "fallback_response": msg.meta.get("fallback_response") if msg.meta else None,
                "semantic_analysis": msg.meta.get("semantic_analysis") if msg.meta else None,
                "divergence_breakdown": msg.meta.get("divergence_breakdown") if msg.meta else None,
                "contract_version": msg.meta.get("contract_version", 1) if msg.meta else 1,
                "synthesis_id": msg.response_id,
                "synthesis_revision": msg.meta.get("revision", 1) if msg.meta else 1,
                "synthesis_response_ids": msg.meta.get("response_ids", []) if msg.meta else [],
                "synthesis_input_hash": msg.meta.get("input_hash") if msg.meta else None,
                "provisional_promoted": msg.meta.get("provisional_promoted", False)
                if msg.meta
                else False,
                "synthesis_usage_call": msg.meta.get("usage_call") if msg.meta else None,
            }
            return msg.content, sreport, meta
        return "Synthesis unavailable.", None, {}

    async def run_synthesis_fn():
        synthesis_usage_call: UsageCall | None = None
        if promote_provisional and provisional_revision is not None:
            scontent = provisional_revision.content
            sreport = provisional_revision.report
            meta = {
                "synthesis_status": "succeeded",
                "synthesis_error": None,
                "contract_version": 1,
                "synthesis_id": f"synth-{debate_id}-a{run_attempt}",
                "synthesis_revision": 1,
                "synthesis_response_ids": list(final_response_ids),
                "synthesis_input_hash": final_input_hash,
                "provisional_promoted": True,
            }
        elif progressive_enabled:
            try:
                final_revision_id = _synthesis_revision_id(
                    debate_id,
                    run_attempt,
                    1,
                    final_input_hash,
                )
                async with async_session_scope() as session:
                    final_revision = await _load_synthesis_revision(
                        session,
                        debate_id,
                        final_revision_id,
                    )
                if final_revision is not None:
                    _assert_final_revision_snapshot_matches(
                        final_revision,
                        synthesis_id=final_revision_id,
                        input_hash=final_input_hash,
                        response_ids=final_response_ids,
                    )
                else:
                    final_revision = await _generate_and_persist_final_synthesis(
                        debate_id=debate_id,
                        run_attempt=run_attempt,
                        prompt=prompt,
                        responses=successful,
                        total_count=len(model_responses),
                        model_order=model_order,
                        backend=backend,
                        user_id=user_id,
                        model_id=model_id,
                        locale=locale,
                        owner_id=execution_owner_id,
                        lease_epoch=lease_epoch,
                    )
                scontent = final_revision.content
                sreport = final_revision.report
                synthesis_usage_call = final_revision.usage_call
                synthesis_succeeded = final_revision.status == "final"
                meta = {
                    "synthesis_status": ("succeeded" if synthesis_succeeded else "failed"),
                    "synthesis_error": (
                        None if synthesis_succeeded else "Final synthesis returned no content."
                    ),
                    "fallback_model": (None if synthesis_succeeded else successful[0].display_name),
                    "fallback_reason": (
                        None
                        if synthesis_succeeded
                        else "Top model response shown because final synthesis failed"
                    ),
                    "fallback_response": (
                        None
                        if synthesis_succeeded
                        else {
                            "model": successful[0].display_name,
                            "content": scontent,
                        }
                    ),
                    "semantic_analysis": (
                        sreport.get("divergence_breakdown") if isinstance(sreport, dict) else None
                    ),
                    "divergence_breakdown": (
                        sreport.get("divergence_breakdown") if isinstance(sreport, dict) else None
                    ),
                    "contract_version": 1,
                    "synthesis_id": f"synth-{debate_id}-a{run_attempt}",
                    "synthesis_revision": 1,
                    "synthesis_response_ids": list(final_response_ids),
                    "synthesis_input_hash": final_input_hash,
                    "provisional_promoted": False,
                }
            except Exception as exc:
                from orchestration.checkpoints import (
                    CheckpointIntegrityError,
                    CheckpointOwnershipLostError,
                )
                from orchestration.execution_lease import ExecutionSupersededError

                if isinstance(
                    exc,
                    (
                        ExecutionSupersededError,
                        CheckpointOwnershipLostError,
                        CheckpointIntegrityError,
                    ),
                ):
                    raise
                logger.error(
                    "arena.final_streaming_synthesis_failed debate_id=%s error=%s",
                    debate_id,
                    exc,
                    exc_info=True,
                )
                top_response = successful[0]
                scontent = (
                    "⚠️ Final synthesis unavailable. Source responses remain "
                    "available.\n\n"
                    f"**{top_response.display_name}:**\n{top_response.content}"
                )
                sreport = None
                meta = {
                    "synthesis_status": "failed",
                    "synthesis_error": sanitize_synthesis_error(str(exc)),
                    "fallback_model": top_response.display_name,
                    "fallback_reason": ("Top model response shown because final synthesis failed"),
                    "fallback_response": {
                        "model": top_response.display_name,
                        "content": scontent,
                    },
                    "semantic_analysis": None,
                    "divergence_breakdown": None,
                    "contract_version": 1,
                    "synthesis_id": f"synth-{debate_id}-a{run_attempt}",
                    "synthesis_revision": 1,
                    "synthesis_response_ids": list(final_response_ids),
                    "synthesis_input_hash": final_input_hash,
                    "provisional_promoted": False,
                }
        else:
            scontent, sreport, meta = await _synthesize_verdict(
                debate_id=debate_id,
                prompt=prompt,
                model_responses=successful,
                usage=usage,
                model_id=model_id,
                locale=locale,
                execution_owner_id=execution_owner_id,
                lease_epoch=lease_epoch,
            )
            meta = {
                **meta,
                "contract_version": 1,
                "synthesis_id": f"synth-{debate_id}-a{run_attempt}",
                "synthesis_revision": 1,
                "synthesis_response_ids": list(final_response_ids),
                "synthesis_input_hash": final_input_hash,
                "provisional_promoted": False,
            }
        meta["synthesis_usage_call"] = _usage_call_to_meta(synthesis_usage_call)
        ssuccess = meta.get("synthesis_status") == "succeeded"

        # Persist synthesis
        async with async_session_scope() as session:
            from models import DebateAttempt
            from orchestration.fencing import assert_execution_ownership
            from sqlalchemy.exc import IntegrityError

            write_lease = _lease_for_arena_write(
                debate_id, run_attempt, execution_owner_id, lease_epoch
            )
            if write_lease is not None:
                await assert_execution_ownership(session, write_lease)
            attempt_result = await session.execute(
                select(DebateAttempt.id).where(
                    DebateAttempt.debate_id == debate_id,
                    DebateAttempt.attempt_number == run_attempt,
                )
            )
            session.add(
                Message(
                    debate_id=debate_id,
                    attempt_id=attempt_result.scalar_one_or_none(),
                    response_id=f"synth-{debate_id}-a{run_attempt}",
                    round_index=2,
                    role="arena_synthesis",
                    persona="Synthesizer",
                    content=scontent,
                    meta={
                        "mode": "arena",
                        "phase": "synthesis",
                        "contract_version": 1,
                        "run_attempt": run_attempt,
                        "revision": 1,
                        "status": "final",
                        "input_hash": final_input_hash,
                        "response_ids": list(final_response_ids),
                        "successful_count": len(successful),
                        "total_count": len(model_responses),
                        "provisional_promoted": bool(meta.get("provisional_promoted", False)),
                        "synthesis_success": ssuccess,
                        "synthesis_report": sreport,
                        "usage_call": meta.get("synthesis_usage_call"),
                        **{
                            key: value
                            for key, value in meta.items()
                            if key != "synthesis_usage_call"
                        },
                    },
                )
            )
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                if not _is_response_identity_conflict(exc):
                    raise
                # P2 #11: After a duplicate conflict, fetch the canonical existing
                # row and return its content instead of the newly computed one.
                # This prevents durable/live divergence when the DB already has
                # a synthesis for this identity.
                existing_result = await session.execute(
                    select(Message).where(
                        Message.debate_id == debate_id,
                        Message.response_id == f"synth-{debate_id}-a{run_attempt}",
                    )
                )
                existing_msg = existing_result.scalars().first()
                if existing_msg:
                    logger.info(
                        "arena_synthesis.conflict_resolved_using_canonical: "
                        "debate_id=%s response_id=%s",
                        debate_id,
                        f"synth-{debate_id}-a{run_attempt}",
                    )
                    existing_meta = existing_msg.meta or {}
                    existing_report = existing_meta.get("synthesis_report")
                    existing_meta_updates = {
                        "synthesis_status": "succeeded"
                        if existing_meta.get("synthesis_success")
                        else "failed",
                        "synthesis_error": existing_meta.get("synthesis_error"),
                        "fallback_model": existing_meta.get("fallback_model"),
                        "fallback_reason": existing_meta.get("fallback_reason"),
                        "fallback_response": existing_meta.get("fallback_response"),
                        "semantic_analysis": existing_meta.get("semantic_analysis"),
                        "divergence_breakdown": existing_meta.get("divergence_breakdown"),
                        "contract_version": existing_meta.get("contract_version", 1),
                        "synthesis_id": existing_msg.response_id,
                        "synthesis_revision": existing_meta.get("revision", 1),
                        "synthesis_response_ids": existing_meta.get("response_ids", []),
                        "synthesis_input_hash": existing_meta.get("input_hash"),
                        "provisional_promoted": existing_meta.get("provisional_promoted", False),
                        "synthesis_usage_call": existing_meta.get("usage_call"),
                    }
                    return existing_msg.content, existing_report, existing_meta_updates
                # No existing row found (unexpected) — fall through with new content.
        return scontent, sreport, meta

    synthesis_content, synthesis_report, meta_updates = await run_with_checkpoint(
        debate_id,
        "arena_synthesis",
        synthesis_input,
        run_synthesis_fn,
        load_synthesis_fn,
        owner_id=execution_owner_id,
        lease_epoch=lease_epoch,
    )
    synthesis_usage_call = _usage_call_from_meta(meta_updates.pop("synthesis_usage_call", None))
    if synthesis_usage_call is not None:
        usage.add_call(synthesis_usage_call)
    synthesis_success = meta_updates.get("synthesis_status") == "succeeded"
    verification_status = "unavailable"
    if isinstance(synthesis_report, dict):
        qm = synthesis_report.get("quality_meta") or {}
        verification_status = qm.get("verification_status", "unavailable")
    elif meta_updates.get("verification_status"):
        verification_status = meta_updates["verification_status"]
    is_verified = verification_status == "verified"
    # The final synthesis is durable here, but the orchestrator owns the
    # terminal publish after Debate.status has been committed. This keeps
    # transport state and durable state in the same order.
    if all_models_terminal_at is not None:
        try:
            from observability.metrics import record_arena_final_convergence

            record_arena_final_convergence((time.monotonic() - all_models_terminal_at) * 1000)
        except Exception:
            logger.debug("arena final convergence metric failed", exc_info=True)

    # Build final meta
    failed_models = [r for r in model_responses if not r.success]
    model_warnings = [
        {
            "model_id": r.model_id,
            "display_name": r.display_name,
            "provider": r.provider,
            "message": r.content or "This model did not return a response.",
            "error_code": r.error_code,
        }
        for r in failed_models
    ]

    final_meta = {
        "mode": "arena",
        "models": [
            {
                "model_id": r.model_id,
                "display_name": r.display_name,
                "provider": r.provider,
                "success": r.success,
                "logo_url": r.logo_url,
                "persona_type": r.persona_type,
                "persona_tagline": r.persona_tagline,
            }
            for r in model_responses
        ],
        "successful_count": len(successful),
        "total_count": len(model_responses),
        "synthesis_success": synthesis_success,
        "synthesis_report": synthesis_report,
        "verification_status": verification_status,
        "is_verified": is_verified,
        "contract_version": 1,
        "synthesis_id": f"synth-{debate_id}-a{run_attempt}",
        "synthesis_revision": 1,
        "synthesis_response_ids": list(final_response_ids),
        "synthesis_input_hash": final_input_hash,
        "provisional_promoted": bool(meta_updates.get("provisional_promoted", False)),
        "model_warnings": model_warnings,
        "usage": usage.snapshot(),
        **meta_updates,
    }

    return ArenaResult(
        final_answer=synthesis_content,
        final_meta=final_meta,
        usage_tracker=usage,
        status="completed" if synthesis_success else "completed_with_warnings",
        model_responses=model_responses,
    )


def sanitize_synthesis_error(error_msg: str) -> str:
    """Sanitize synthesis errors to avoid exposing sensitive details, stack traces, API keys, or provider internals."""
    if not error_msg:
        return "An unknown error occurred during synthesis."

    # Redact common key/token patterns
    error_msg = re.sub(r"sk-[a-zA-Z0-9\-_]{12,}", "[REDACTED_API_KEY]", error_msg)
    error_msg = re.sub(
        r"Bearer\s+[a-zA-Z0-9\-_.]+", "Bearer [REDACTED]", error_msg, flags=re.IGNORECASE
    )

    sensitive_words = [
        "litellm",
        "openai",
        "anthropic",
        "gemini",
        "google",
        "cohere",
        "groq",
        "together",
        "ollama",
        "api_key",
        "api-key",
        "credential",
        "secret",
        "token",
        "auth",
        "unauthorized",
        "forbidden",
        "rate_limit",
        "rate-limit",
        "quota",
        "billing",
        "invalid_request",
        "bad_request",
        "json.decoder",
        "json_parse",
        "parse_error",
        "traceback",
        "stack_trace",
        "line ",
        "file ",
        "exception",
        "connection",
        "timeout",
        "status_code",
        "400",
        "401",
        "403",
        "429",
        "500",
    ]

    msg_lower = error_msg.lower()
    for word in sensitive_words:
        if word in msg_lower:
            return "The structured synthesis service encountered a validation or parsing error. Raw model responses have been preserved."

    if len(error_msg) > 120 or "\n" in error_msg:
        return "The structured synthesis service encountered a validation or parsing error. Raw model responses have been preserved."

    return error_msg


async def _synthesize_verdict(
    *,
    debate_id: str,
    prompt: str,
    model_responses: List[ArenaModelResponse],
    usage: UsageAccumulator,
    model_id: str | None = None,
    locale: str | None = None,
    execution_owner_id: str | None = None,
    lease_epoch: int | None = None,
) -> tuple[str, dict | None, dict]:
    """Produce the final synthesized verdict and structured decision report from all model responses."""
    from reporting.synthesizer import StructuredSynthesisError, generate_decision_report

    responses_list = [{"persona": r.display_name, "content": r.content} for r in model_responses]

    try:
        report = await generate_decision_report(
            prompt=prompt,
            responses=responses_list,
            debate_id=debate_id,
            locale=locale,
            model_override=model_id,
            usage=usage,
            execution_owner_id=execution_owner_id,
            lease_epoch=lease_epoch,
        )
        meta_updates = {
            "synthesis_status": "succeeded",
            "synthesis_error": None,
            "fallback_model": None,
            "fallback_reason": None,
            "fallback_response": None,
            "semantic_analysis": report.divergence_breakdown,
            "divergence_breakdown": report.divergence_breakdown,
        }
        return report.executive_summary or report.title, report.model_dump(), meta_updates
    except StructuredSynthesisError as e:
        logger.error(f"Arena synthesis failed with StructuredSynthesisError: {e}")
        successful_responses = [r for r in model_responses if r.success]
        if successful_responses:
            fallback_resp = successful_responses[0]
            fallback_model_name = f"{fallback_resp.display_name} ({fallback_resp.provider.capitalize() if fallback_resp.provider else ''})"
            fallback_content = (
                f"⚠️ Synthesis unavailable. Here is the top response:\n\n"
                f"**{fallback_resp.display_name}:**\n{fallback_resp.content}"
            )
        else:
            fallback_model_name = "Synthesizer"
            fallback_content = "⚠️ Synthesis unavailable. All model calls failed."
        meta_updates = {
            "synthesis_status": "failed",
            "synthesis_error": sanitize_synthesis_error(str(e)),
            "fallback_model": fallback_model_name,
            "fallback_reason": "Top model response shown because structured synthesis failed",
            "fallback_response": {
                "model": fallback_model_name,
                "content": fallback_content,
            },
            "semantic_analysis": e.semantic_analysis,
            "divergence_breakdown": e.semantic_analysis,
        }
        return fallback_content, None, meta_updates
    except Exception as e:
        logger.error(f"Arena synthesis failed with general exception: {e}")
        successful_responses = [r for r in model_responses if r.success]
        if successful_responses:
            fallback_resp = successful_responses[0]
            fallback_model_name = f"{fallback_resp.display_name} ({fallback_resp.provider.capitalize() if fallback_resp.provider else ''})"
            fallback_content = (
                f"⚠️ Synthesis unavailable. Here is the top response:\n\n"
                f"**{fallback_resp.display_name}:**\n{fallback_resp.content}"
            )
        else:
            fallback_model_name = "Synthesizer"
            fallback_content = "⚠️ Synthesis unavailable. All model calls failed."
        meta_updates = {
            "synthesis_status": "failed",
            "synthesis_error": sanitize_synthesis_error(str(e)),
            "fallback_model": fallback_model_name,
            "fallback_reason": "Top model response shown because structured synthesis failed",
            "fallback_response": {
                "model": fallback_model_name,
                "content": fallback_content,
            },
            "semantic_analysis": None,
            "divergence_breakdown": None,
        }
        return fallback_content, None, meta_updates
