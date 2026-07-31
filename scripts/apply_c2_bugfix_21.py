from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name == 'scripts' else Path.cwd()


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding='utf-8')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one match, found {count}')
    return text.replace(old, new, 1)


def replace_all_exact(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f'{label}: expected {expected} matches, found {count}')
    return text.replace(old, new)


# ---------------------------------------------------------------------------
# Provider health: user-scoped BYOK failures must never mutate shared circuits.
# ---------------------------------------------------------------------------
rel = 'apps/api/model_gateway/provider_health.py'
text = read(rel)
text = replace_once(
    text,
    'def record_success(provider: str, canonical_model_id: str | None = None):\n'
    '    """Record a successful call to the provider, resetting failure counts."""\n'
    '    redis_client = get_redis()\n',
    'def record_success(\n'
    '    provider: str,\n'
    '    canonical_model_id: str | None = None,\n'
    '    *,\n'
    '    credential_scope: str = "server",\n'
    '):\n'
    '    """Record a shared-provider success.\n\n'
    '    User-supplied BYOK calls are isolated from shared provider health: a\n'
    '    successful user key must not reset failures observed by hosted routes.\n'
    '    """\n'
    '    if credential_scope == "user":\n'
    '        return\n'
    '    redis_client = get_redis()\n',
    'provider_health record_success scope',
)
text = replace_once(
    text,
    'def record_failure(\n'
    '    provider: str,\n'
    '    failure_code: str,\n'
    '    error_msg: str,\n'
    '    canonical_model_id: str | None = None,\n'
    '):\n'
    '    """Record a failure for the provider and update the circuit breaker state."""\n'
    '    redis_client = get_redis()\n',
    'def record_failure(\n'
    '    provider: str,\n'
    '    failure_code: str,\n'
    '    error_msg: str,\n'
    '    canonical_model_id: str | None = None,\n'
    '    *,\n'
    '    credential_scope: str = "server",\n'
    '):\n'
    '    """Record a shared-provider failure and update the circuit breaker.\n\n'
    '    Failures from a user-owned BYOK credential are tenant-local. They may\n'
    '    represent an invalid key, exhausted personal balance, or personal quota\n'
    '    and therefore must never open or increment a circuit shared by others.\n'
    '    """\n'
    '    if credential_scope == "user":\n'
    '        logger.info(\n'
    '            "Ignoring user-scoped provider health mutation: provider=%s model=%s code=%s",\n'
    '            provider,\n'
    '            canonical_model_id,\n'
    '            failure_code,\n'
    '        )\n'
    '        return\n'
    '    redis_client = get_redis()\n',
    'provider_health record_failure scope',
)
write(rel, text)


# ---------------------------------------------------------------------------
# Gateway: propagate credential scope to provider-health writes.
# ---------------------------------------------------------------------------
rel = 'apps/api/model_gateway/__init__.py'
text = read(rel)
text = replace_once(
    text,
    '        current_api_key = None\n'
    '        if db_session and request.user_id:\n',
    '        current_api_key = None\n'
    '        credential_scope = "server"\n'
    '        if db_session and request.user_id:\n',
    'gateway credential scope init',
)
text = replace_once(
    text,
    '                if resolved and resolved.source == "user":\n'
    '                    current_api_key = resolved.key\n'
    '                    logger.info("Using user BYOK key for provider=%s model=%s user=%s", provider, model_to_call, request.user_id)\n',
    '                if resolved and resolved.source == "user":\n'
    '                    current_api_key = resolved.key\n'
    '                    credential_scope = "user"\n'
    '                    logger.info("Using user BYOK key for provider=%s model=%s user=%s", provider, model_to_call, request.user_id)\n',
    'gateway credential scope BYOK',
)
text = replace_once(
    text,
    '        if not current_api_key and request.api_key:\n'
    '            current_api_key = request.api_key\n',
    '        if not current_api_key and request.api_key:\n'
    '            current_api_key = request.api_key\n'
    '            credential_scope = "user"\n',
    'gateway request api key scope',
)
text = replace_once(
    text,
    '                record_success(provider)\n',
    '                record_success(provider, credential_scope=credential_scope)\n',
    'gateway direct success scope',
)
text = replace_once(
    text,
    '                record_failure(provider, result.error_code or "unknown", result.error_message or "")\n',
    '                record_failure(\n'
    '                    provider,\n'
    '                    result.error_code or "unknown",\n'
    '                    result.error_message or "",\n'
    '                    credential_scope=credential_scope,\n'
    '                )\n',
    'gateway direct result failure scope',
)
text = replace_once(
    text,
    '            record_failure(provider, "unknown", str(e))\n',
    '            record_failure(\n'
    '                provider,\n'
    '                "unknown",\n'
    '                str(e),\n'
    '                credential_scope=credential_scope,\n'
    '            )\n',
    'gateway direct exception failure scope',
)
text = replace_once(
    text,
    '    if user_id and not api_key:\n'
    '        try:\n',
    '    credential_scope = "user" if api_key else "server"\n'
    '    if user_id and not api_key:\n'
    '        try:\n',
    'gateway stream credential scope init',
)
text = replace_once(
    text,
    '                if resolved:\n'
    '                    api_key = resolved.key\n',
    '                if resolved:\n'
    '                    api_key = resolved.key\n'
    '                    credential_scope = "user"\n',
    'gateway stream BYOK scope',
)
text = replace_once(
    text,
    '        record_success(provider, canonical_model_id=canonical_model_id)\n',
    '        record_success(\n'
    '            provider,\n'
    '            canonical_model_id=canonical_model_id,\n'
    '            credential_scope=credential_scope,\n'
    '        )\n',
    'gateway stream success scope',
)
text = replace_once(
    text,
    '            canonical_model_id=canonical_model_id,\n'
    '        )\n\n'
    '    return result\n',
    '            canonical_model_id=canonical_model_id,\n'
    '            credential_scope=credential_scope,\n'
    '        )\n\n'
    '    return result\n',
    'gateway stream failure scope',
)
write(rel, text)


# ---------------------------------------------------------------------------
# Agent bridge: preserve concrete error code for retry classification.
# ---------------------------------------------------------------------------
rel = 'apps/api/model_gateway/agent_bridge.py'
text = read(rel)
text = replace_once(
    text,
    '        raise TransientLLMError(\n'
    '            gw_res.error_message or "LLM response contained no content",\n'
    '            error_code=gw_res.error_code\n'
    '        )\n',
    '        raise TransientLLMError(\n'
    '            gw_res.error_message or "LLM response contained no content",\n'
    '            error_code=gw_res.error_code,\n'
    '        )\n',
    'agent bridge formatting',
)
write(rel, text)


# ---------------------------------------------------------------------------
# Agents: effective-model attribution, no duplicate health mutation, fail-fast
# for deterministic errors.
# ---------------------------------------------------------------------------
rel = 'apps/api/agents.py'
text = read(rel)
text = replace_once(
    text,
    '        target = resolve_model_target(model_id or model_override)\n',
    '        target = resolve_model_target(model_override or model_id)\n',
    'agents prefer model override',
)
text = replace_once(
    text,
    '    effective_model_id = model_override or model_cfg.id\n',
    '    effective_model_id = model_override or model_id or canonical_model_id\n',
    'agents effective model without conditional model_cfg',
)
text = replace_once(
    text,
    '        # Record successful call\n'
    '        record_success(provider_name, canonical_model_id=canonical_model_id)\n\n',
    '        # Provider health is recorded once inside the gateway using the\n'
    '        # actual routed model and credential scope. Do not double-count here.\n\n',
    'agents duplicate success health',
)
text = replace_once(
    text,
    '        record_failure(provider_name, "timeout", "LLM call timed out", canonical_model_id=canonical_model_id)\n',
    '        # The gateway owns provider-health accounting.\n',
    'agents duplicate timeout health',
)
text = replace_once(
    text,
    '        record_failure(provider_name, "unknown", str(exc), canonical_model_id=canonical_model_id)\n',
    '        # The gateway owns provider-health accounting.\n',
    'agents duplicate generic health',
)
text = replace_once(
    text,
    'async def call_llm_with_retry(\n',
    'NON_RETRYABLE_LLM_ERROR_CODES = {\n'
    '    "invalid_credentials",\n'
    '    "insufficient_balance",\n'
    '    "model_key_unresolved",\n'
    '    "unknown_model",\n'
    '}\n\n\n'
    'async def call_llm_with_retry(\n',
    'agents nonretryable constant',
)
text = replace_once(
    text,
    '        except TransientLLMError as exc:\n'
    '            last_exc = exc\n'
    '            if attempt >= max_attempts:\n'
    '                raise\n',
    '        except TransientLLMError as exc:\n'
    '            last_exc = exc\n'
    '            if exc.error_code in NON_RETRYABLE_LLM_ERROR_CODES:\n'
    '                raise\n'
    '            if attempt >= max_attempts:\n'
    '                raise\n',
    'agents deterministic retry stop',
)
write(rel, text)


# ---------------------------------------------------------------------------
# Streaming adapters: treat hidden reasoning/thinking chunks as activity without
# exposing them. Emit one empty lifecycle delta so UI can say "reasoning".
# ---------------------------------------------------------------------------
rel = 'apps/api/model_gateway/adapters.py'
text = read(rel)
text = replace_once(
    text,
    'logger = logging.getLogger("model_gateway.adapters")\n\n',
    'logger = logging.getLogger("model_gateway.adapters")\n\n\n'
    'def _has_hidden_reasoning_activity(delta: Any) -> bool:\n'
    '    """Return True when a provider emitted non-user-visible reasoning.\n\n'
    '    The content is intentionally not surfaced; this signal only prevents a\n'
    '    healthy reasoning model from being mistaken for a silent connection.\n'
    '    """\n'
    '    if delta is None:\n'
    '        return False\n'
    '    for name in ("reasoning_content", "reasoning", "thinking"):\n'
    '        value = getattr(delta, name, None)\n'
    '        if value:\n'
    '            return True\n'
    '    return False\n\n',
    'adapters reasoning helper',
)
text = replace_all_exact(
    text,
    '        ttft_ms: float | None = None\n',
    '        ttft_ms: float | None = None\n'
    '        activity_seen = False\n'
    '        activity_announced = False\n',
    2,
    'adapters activity state',
)
text = replace_all_exact(
    text,
    '                if ttft_ms is None:\n'
    '                    timeout_for_chunk = min(first_token_timeout_s, total_timeout_s - total_elapsed)\n'
    '                else:\n'
    '                    timeout_for_chunk = min(active_stream_timeout_s, total_timeout_s - total_elapsed)\n',
    '                if not activity_seen:\n'
    '                    timeout_for_chunk = min(first_token_timeout_s, total_timeout_s - total_elapsed)\n'
    '                else:\n'
    '                    timeout_for_chunk = min(active_stream_timeout_s, total_timeout_s - total_elapsed)\n',
    2,
    'adapters staged timeout activity',
)
text = replace_all_exact(
    text,
    '                except asyncio.TimeoutError:\n'
    '                    if ttft_ms is None:\n'
    '                        raise asyncio.TimeoutError("stream_first_token_timeout") from None\n'
    '                    else:\n'
    '                        raise asyncio.TimeoutError("stream_active_stall") from None\n\n'
    '                delta = chunk.choices[0].delta if chunk.choices else None\n'
    '                text = getattr(delta, "content", None) or "" if delta else ""\n'
    '                if text:\n'
    '                    now = time.monotonic()\n'
    '                    if ttft_ms is None:\n'
    '                        ttft_ms = (now - start_ts) * 1000\n'
    '                    accumulated += text\n'
    '                    seq += 1\n'
    '                    await on_delta(ModelDelta(text=text, sequence=seq, accumulated_chars=len(accumulated)))\n',
    '                except asyncio.TimeoutError:\n'
    '                    if not activity_seen:\n'
    '                        raise asyncio.TimeoutError("stream_first_token_timeout") from None\n'
    '                    raise asyncio.TimeoutError("stream_active_stall") from None\n\n'
    '                delta = chunk.choices[0].delta if chunk.choices else None\n'
    '                text = getattr(delta, "content", None) or "" if delta else ""\n'
    '                hidden_activity = _has_hidden_reasoning_activity(delta)\n'
    '                if text or hidden_activity:\n'
    '                    activity_seen = True\n'
    '                if hidden_activity and not text and not activity_announced:\n'
    '                    activity_announced = True\n'
    '                    seq += 1\n'
    '                    await on_delta(\n'
    '                        ModelDelta(text="", sequence=seq, accumulated_chars=len(accumulated))\n'
    '                    )\n'
    '                if text:\n'
    '                    now = time.monotonic()\n'
    '                    if ttft_ms is None:\n'
    '                        ttft_ms = (now - start_ts) * 1000\n'
    '                    accumulated += text\n'
    '                    seq += 1\n'
    '                    await on_delta(ModelDelta(text=text, sequence=seq, accumulated_chars=len(accumulated)))\n',
    2,
    'adapters reasoning-aware loop',
)
write(rel, text)


# ---------------------------------------------------------------------------
# Arena engine: deterministic failures skip fallback; quorum-cancelled models
# receive persisted terminal responses instead of ghost cards.
# ---------------------------------------------------------------------------
rel = 'apps/api/arena/engine.py'
text = read(rel)
text = replace_once(
    text,
    '                    else:\n'
    '                        # Streaming returned failure — try non-streaming fallback\n'
    '                        # within the same timeout window before giving up.\n'
    '                        logger.warning(\n',
    '                    else:\n'
    '                        non_retryable_stream_errors = {\n'
    '                            "invalid_credentials",\n'
    '                            "insufficient_balance",\n'
    '                            "model_key_unresolved",\n'
    '                            "unknown_model",\n'
    '                        }\n'
    '                        if result.error_code in non_retryable_stream_errors:\n'
    '                            return ArenaModelResponse(\n'
    '                                model_id=model_info.id,\n'
    '                                display_name=model_info.display_name,\n'
    '                                provider=model_info.provider,\n'
    '                                content=f"⚠️ This model failed to respond: {result.error_message}",\n'
    '                                success=False,\n'
    '                                logo_url=model_info.logo_url,\n'
    '                                persona_type=model_info.persona_type,\n'
    '                                persona_tagline=model_info.persona_tagline,\n'
    '                                error=result.error_message,\n'
    '                                error_code=result.error_code,\n'
    '                            ), None\n\n'
    '                        # Transient streaming failures may use the non-streaming\n'
    '                        # route once within the same total deadline.\n'
    '                        logger.warning(\n',
    'arena deterministic fallback',
)
text = replace_once(
    text,
    '        tasks = [\n'
    '            asyncio.create_task(_call_and_persist(model))\n'
    '            for model in arena_models\n'
    '            if model.id not in completed_models\n'
    '        ]\n',
    '        tasks: list[asyncio.Task] = []\n'
    '        task_models: dict[asyncio.Task, object] = {}\n'
    '        for model in arena_models:\n'
    '            if model.id in completed_models:\n'
    '                continue\n'
    '            task = asyncio.create_task(_call_and_persist(model))\n'
    '            tasks.append(task)\n'
    '            task_models[task] = model\n',
    'arena task model mapping',
)
marker = '            all_models_terminal_at = time.monotonic()\n\n            if provisional_task is not None:\n'
insert = '''            if pending_set:\n                skipped_tasks = tuple(pending_set)\n                for pending_task in skipped_tasks:\n                    pending_task.cancel()\n                await asyncio.gather(*skipped_tasks, return_exceptions=True)\n\n                for pending_task in skipped_tasks:\n                    model_info = task_models[pending_task]\n                    retry_generation = 0\n                    response_id = (\n                        f"resp-{debate_id}-"\n                        f"a{run_attempt}-"\n                        f"g{retry_generation}-"\n                        f"{model_info.id}"\n                    )\n                    lifecycle_payload = {\n                        "contract_version": 1,\n                        "response_id": response_id,\n                        "model_id": model_info.id,\n                        "display_name": model_info.display_name,\n                        "provider": model_info.provider,\n                        "run_attempt": run_attempt,\n                        "retry_generation": retry_generation,\n                    }\n                    skipped_response = ArenaModelResponse(\n                        model_id=model_info.id,\n                        display_name=model_info.display_name,\n                        provider=model_info.provider,\n                        content=(\n                            "This model was still running when the response quorum "\n                            "finalized the decision."\n                        ),\n                        success=False,\n                        logo_url=model_info.logo_url,\n                        persona_type=model_info.persona_type,\n                        persona_tagline=model_info.persona_tagline,\n                        error="Finalized after quorum before this model completed.",\n                        error_code="quorum_finalized",\n                        response_id=response_id,\n                        run_attempt=run_attempt,\n                        retry_generation=retry_generation,\n                    )\n                    await _publish_lifecycle_best_effort(\n                        backend,\n                        f"debate:{debate_id}",\n                        {"type": "model_response_persisting", **lifecycle_payload},\n                    )\n                    try:\n                        async with async_session_scope() as session:\n                            await persist_and_publish_arena_response(\n                                session,\n                                backend,\n                                debate_id,\n                                skipped_response,\n                                owner_id=execution_owner_id,\n                                lease_epoch=lease_epoch,\n                            )\n                    except Exception as persist_exc:\n                        logger.warning(\n                            "Failed to persist quorum-finalized model %s: %s",\n                            model_info.id,\n                            persist_exc,\n                        )\n                    await _publish_lifecycle_best_effort(\n                        backend,\n                        f"debate:{debate_id}",\n                        {\n                            "type": "model_response_failed",\n                            **lifecycle_payload,\n                            "error": skipped_response.error,\n                            "error_code": skipped_response.error_code,\n                        },\n                    )\n                    responses.append(skipped_response)\n                pending_set.clear()\n\n            all_models_terminal_at = time.monotonic()\n\n            if provisional_task is not None:\n'''
text = replace_once(text, marker, insert, 'arena quorum terminalization')
write(rel, text)


# ---------------------------------------------------------------------------
# Debate: continue in degraded mode when minimum successful seats exist.
# ---------------------------------------------------------------------------
rel = 'apps/api/parliament/engine.py'
text = read(rel)
text = replace_once(
    text,
    '    round_history: list[dict[str, Any]] = []\n'
    '    seat_usage: list[dict[str, Any]] = []\n',
    '    round_history: list[dict[str, Any]] = []\n'
    '    seat_usage: list[dict[str, Any]] = []\n'
    '    degraded_rounds: list[int] = []\n',
    'parliament degraded tracking',
)
text = replace_once(
    text,
    '        if outcome.status == "failed":\n',
    '        if outcome.status == "degraded":\n'
    '            degraded_rounds.append(outcome.round_index)\n'
    '            await backend.publish(\n'
    '                f"debate:{debate_id}",\n'
    '                {\n'
    '                    "type": "notice",\n'
    '                    "debate_id": str(debate_id),\n'
    '                    "round": outcome.round_index,\n'
    '                    "payload": {\n'
    '                        "message": "Round continued with partial model participation.",\n'
    '                        "note": "degraded",\n'
    '                    },\n'
    '                },\n'
    '            )\n'
    '        if outcome.status == "failed":\n',
    'parliament degraded event',
)
text = replace_once(
    text,
    '    status = "completed"\n',
    '    status = "completed_with_warnings" if degraded_rounds else "completed"\n',
    'parliament degraded final status',
)
text = replace_once(
    text,
    '        "scores": scores,\n'
    '        "usage": usage.snapshot(),\n',
    '        "scores": scores,\n'
    '        "degraded_rounds": degraded_rounds,\n'
    '        "usage": usage.snapshot(),\n',
    'parliament degraded metadata',
)
text = replace_once(
    text,
    '    if fail_fast and (fail_ratio > fail_ratio_limit or success_count < min_required):\n'
    '        outcome_status = "failed"\n'
    '        outcome_reason = "seat_failure_threshold_exceeded"\n',
    '    if fail_fast and success_count < min_required:\n'
    '        outcome_status = "failed"\n'
    '        outcome_reason = "minimum_successful_seats_not_met"\n'
    '    elif fail_ratio > fail_ratio_limit:\n'
    '        outcome_status = "degraded"\n'
    '        outcome_reason = "seat_failure_threshold_exceeded"\n',
    'parliament degraded tolerance',
)
write(rel, text)


# ---------------------------------------------------------------------------
# Frontend stream state: monotonic lifecycle; terminal states are sticky.
# ---------------------------------------------------------------------------
rel = 'apps/web/lib/workspace/streamReducer.ts'
text = read(rel)
text = replace_once(
    text,
    'function stateForLifecycle(s: ModelState): ModelState {\n'
    '  return s;\n'
    '}\n',
    'const MODEL_STATE_RANK: Record<ModelState, number> = {\n'
    '  queued: 0,\n'
    '  connecting: 1,\n'
    '  started: 2,\n'
    '  streaming: 3,\n'
    '  persisting: 4,\n'
    '  completed: 5,\n'
    '  failed: 5,\n'
    '};\n\n'
    'function shouldApplyLifecycle(current: ModelState | undefined, incoming: ModelState): boolean {\n'
    '  if (!current) return true;\n'
    '  if (current === "completed" || current === "failed") return false;\n'
    '  return MODEL_STATE_RANK[incoming] >= MODEL_STATE_RANK[current];\n'
    '}\n',
    'stream reducer lifecycle ranks',
)
text = replace_once(
    text,
    '      const { response_id, model_id, display_name, provider } = action.payload;\n'
    '      const buf: StreamingModelBuffer = {\n',
    '      const { response_id, model_id, display_name, provider } = action.payload;\n'
    '      const existing = state.buffers.get(response_id);\n'
    '      if (existing && !shouldApplyLifecycle(existing.state, "queued")) return state;\n'
    '      const buf: StreamingModelBuffer = {\n',
    'stream reducer queued monotonic',
)
text = replace_once(
    text,
    '      let buf = state.buffers.get(response_id);\n'
    '      if (!buf) {\n',
    '      let buf = state.buffers.get(response_id);\n'
    '      if (buf && !shouldApplyLifecycle(buf.state, "connecting")) return state;\n'
    '      if (!buf) {\n',
    'stream reducer connecting monotonic',
)
idx = text.find('      let buf = state.buffers.get(response_id);\n      if (!buf) {', text.find('case "RESPONSE_STARTED"'))
if idx == -1:
    raise RuntimeError('stream reducer started occurrence missing')
old = '      let buf = state.buffers.get(response_id);\n      if (!buf) {'
new = '      let buf = state.buffers.get(response_id);\n      if (buf && !shouldApplyLifecycle(buf.state, "started")) return state;\n      if (!buf) {'
text = text[:idx] + text[idx:].replace(old, new, 1)
text = replace_once(
    text,
    '      const buf = state.buffers.get(action.payload.response_id);\n'
    '      if (!buf) return state;\n',
    '      const buf = state.buffers.get(action.payload.response_id);\n'
    '      if (!buf || !shouldApplyLifecycle(buf.state, "persisting")) return state;\n',
    'stream reducer persisting monotonic',
)
text = replace_once(
    text,
    '      const buf = state.buffers.get(response_id);\n'
    '      if (!buf) return state;\n'
    '      // Track G: Retain completed buffer with accumulated text until persistence arrives\n',
    '      const buf = state.buffers.get(response_id);\n'
    '      if (!buf || !shouldApplyLifecycle(buf.state, "completed")) return state;\n'
    '      // Track G: Retain completed buffer with accumulated text until persistence arrives\n',
    'stream reducer completed monotonic',
)
text = replace_once(
    text,
    '      if (buf) {\n'
    '        // Existing buffer — mark as failed\n',
    '      if (buf) {\n'
    '        if (!shouldApplyLifecycle(buf.state, "failed")) return state;\n'
    '        // Existing buffer — mark as failed\n',
    'stream reducer failed monotonic',
)
write(rel, text)


# ---------------------------------------------------------------------------
# Synthesis replay: duplicate STARTED must not erase visible content.
# ---------------------------------------------------------------------------
rel = 'apps/web/lib/workspace/synthesisReducer.ts'
text = read(rel)
text = replace_once(
    text,
    '    case "STARTED":\n'
    '      if (isStale(state, action.payload)) return state;\n'
    '      return {\n',
    '    case "STARTED": {\n'
    '      if (isStale(state, action.payload)) return state;\n'
    '      const sameRevision =\n'
    '        state.synthesisId === action.payload.synthesis_id\n'
    '        && state.runAttempt === action.payload.run_attempt\n'
    '        && state.revision === action.payload.revision;\n'
    '      if (sameRevision && state.status !== "idle") return state;\n'
    '      return {\n',
    'synthesis replay guard open',
)
text = replace_once(
    text,
    '        lastDeltaSequence: 0,\n'
    '      };\n'
    '    case "DELTA": {\n',
    '        lastDeltaSequence: 0,\n'
    '      };\n'
    '    }\n'
    '    case "DELTA": {\n',
    'synthesis replay guard close',
)
write(rel, text)


# ---------------------------------------------------------------------------
# Zod coverage for delta events.
# ---------------------------------------------------------------------------
rel = 'apps/web/lib/api/arenaSchemas.ts'
text = read(rel)
text = replace_once(
    text,
    'export const modelLifecycleSchema = z.object({\n',
    'export const modelResponseDeltaSchema = z.object({\n'
    '  type: z.literal("model_response_delta"),\n'
    '  response_id: z.string().min(1),\n'
    '  model_id: z.string().default(""),\n'
    '  display_name: z.string().optional(),\n'
    '  provider: z.string().optional(),\n'
    '  text: z.string(),\n'
    '  delta_sequence: z.number().int().nonnegative(),\n'
    '  accumulated_chars: z.number().int().nonnegative().optional(),\n'
    '  run_attempt: z.number().int().nonnegative().optional(),\n'
    '  retry_generation: z.number().int().nonnegative().optional(),\n'
    '}).passthrough();\n\n'
    'export const synthesisDeltaSchema = z.object({\n'
    '  type: z.literal("arena_synthesis_delta").optional(),\n'
    '  synthesis_id: z.string().min(1).optional(),\n'
    '  response_id: z.string().min(1).optional(),\n'
    '  run_attempt: z.number().int().nonnegative(),\n'
    '  revision: z.number().int().nonnegative(),\n'
    '  status: z.enum(["provisional", "final"]),\n'
    '  text: z.string(),\n'
    '  delta_sequence: z.number().int().nonnegative(),\n'
    '  input_hash: z.string().optional(),\n'
    '  response_ids: z.array(z.string()).optional(),\n'
    '  successful_count: z.number().int().nonnegative().optional(),\n'
    '  total_count: z.number().int().nonnegative().optional(),\n'
    '}).refine(\n'
    '  value => Boolean(value.synthesis_id || value.response_id),\n'
    '  { message: "synthesis_id or response_id is required" },\n'
    ');\n\n'
    'export const modelLifecycleSchema = z.object({\n',
    'arena zod delta schemas',
)
text = replace_once(
    text,
    'export function parseArenaBoundaryEvent(raw: unknown) {\n'
    '  return arenaBoundaryEventSchema.safeParse(flattenEnvelope(raw));\n'
    '}\n',
    'export function parseArenaBoundaryEvent(raw: unknown) {\n'
    '  return arenaBoundaryEventSchema.safeParse(flattenEnvelope(raw));\n'
    '}\n\n'
    'export function parseModelResponseDelta(raw: unknown) {\n'
    '  return modelResponseDeltaSchema.safeParse(flattenEnvelope(raw));\n'
    '}\n\n'
    'export function parseSynthesisDelta(raw: unknown) {\n'
    '  return synthesisDeltaSchema.safeParse(flattenEnvelope(raw));\n'
    '}\n',
    'arena zod delta parsers',
)
write(rel, text)


# ---------------------------------------------------------------------------
# Workspace hook: validate deltas with Zod and dedup before reducers.
# ---------------------------------------------------------------------------
rel = 'apps/web/hooks/useRunWorkspace.ts'
text = read(rel)
text = replace_once(
    text,
    '  formatArenaSchemaDiagnostic,\n'
    '  parseArenaBoundaryEvent,\n',
    '  formatArenaSchemaDiagnostic,\n'
    '  parseArenaBoundaryEvent,\n'
    '  parseModelResponseDelta,\n'
    '  parseSynthesisDelta,\n',
    'workspace import delta parsers',
)
text = replace_once(
    text,
    '        if (eventType === "arena_synthesis_delta") {\n'
    '          const payload = lastEvent.payload || lastEvent;\n'
    '          if (!isValidSynthesisDeltaPayload(payload)) {\n'
    '            console.warn("[arena-contract] Invalid synthesis delta dropped");\n'
    '            return;\n'
    '          }\n'
    '          dispatchSynthesis({ type: "DELTA", payload });\n'
    '          return;\n'
    '        }\n',
    '        if (lastEvent.id && seenEventIdsRef.current.has(lastEvent.id)) return;\n'
    '        if (lastEvent.id) seenEventIdsRef.current.add(lastEvent.id);\n\n'
    '        if (eventType === "arena_synthesis_delta") {\n'
    '          const parsed = parseSynthesisDelta(lastEvent);\n'
    '          if (!parsed.success) {\n'
    '            console.warn(\n'
    '              `[arena-contract] Invalid synthesis delta dropped: ${formatArenaSchemaDiagnostic(parsed.error)}`,\n'
    '            );\n'
    '            return;\n'
    '          }\n'
    '          dispatchSynthesis({ type: "DELTA", payload: parsed.data });\n'
    '          return;\n'
    '        }\n',
    'workspace synthesis zod and early dedup',
)
text = replace_once(
    text,
    '          const p = validatedBoundary ?? lastEvent.payload ?? lastEvent;\n'
    '          if (eventType === "model_response_delta") {\n'
    '            firstDeltaMarkedRef.current ||\n'
    '              (performance.mark?.("sse_first_delta"),\n'
    '              (firstDeltaMarkedRef.current = true));\n'
    '            queueDelta(p);\n'
    '            return;\n'
    '          }\n',
    '          let p = validatedBoundary ?? lastEvent.payload ?? lastEvent;\n'
    '          if (eventType === "model_response_delta") {\n'
    '            const parsed = parseModelResponseDelta(lastEvent);\n'
    '            if (!parsed.success) {\n'
    '              console.warn(\n'
    '                `[arena-contract] Invalid model delta dropped: ${formatArenaSchemaDiagnostic(parsed.error)}`,\n'
    '              );\n'
    '              return;\n'
    '            }\n'
    '            p = parsed.data;\n'
    '            firstDeltaMarkedRef.current ||\n'
    '              (performance.mark?.("sse_first_delta"),\n'
    '              (firstDeltaMarkedRef.current = true));\n'
    '            queueDelta(p);\n'
    '            return;\n'
    '          }\n',
    'workspace model delta zod',
)
text = replace_once(
    text,
    '  const appendEventOnce = useCallback((event: TimelineEvent) => {\n'
    '    if (seenEventIdsRef.current.has(event.id)) return;\n'
    '    seenEventIdsRef.current.add(event.id);\n'
    '    setEvents((prev) => [...prev, event]);\n'
    '  }, []);\n',
    '  const appendEventOnce = useCallback((event: TimelineEvent) => {\n'
    '    setEvents((prev) => {\n'
    '      if (prev.some(item => item.id === event.id)) return prev;\n'
    '      return [...prev, event];\n'
    '    });\n'
    '  }, []);\n',
    'workspace timeline append after early dedup',
)
text = text.replace('  isValidSynthesisDeltaPayload,\n', '')
write(rel, text)


# ---------------------------------------------------------------------------
# UX: compact mobile cards and explicit reasoning state; failed fallback copy.
# ---------------------------------------------------------------------------
rel = 'apps/web/components/arena/ArenaRunView.tsx'
text = read(rel)
text = replace_all_exact(text, 'className="min-h-[300px]"', 'className="min-h-[220px]"', 3, 'mobile arena card height')
write(rel, text)

rel = 'apps/web/components/arena/ModelCard.tsx'
text = read(rel)
text = replace_once(
    text,
    '    // Content looks normal — not an error\n'
    '    return { friendly: "", technical: null };\n',
    '    // A failed response may intentionally carry a user-facing terminal\n'
    '    // explanation (for example quorum finalization). Preserve it.\n'
    '    return { friendly: raw, technical: null };\n',
    'model card failed friendly fallback',
)
text = replace_once(
    text,
    '                    ) : state === "queued" || state === "connecting" ? (\n'
    '                        <div className="flex items-center gap-2 text-sm text-muted-foreground">\n'
    '                            <Loader2 className="h-4 w-4 animate-spin" />\n'
    '                            <span>Waiting for model...</span>\n'
    '                        </div>\n'
    '                    ) : (\n'
    '                        <span className="italic text-muted-foreground">No response received.</span>\n'
    '                    )}\n',
    '                    ) : state === "queued" || state === "connecting" ? (\n'
    '                        <div className="flex items-center gap-2 text-sm text-muted-foreground">\n'
    '                            <Loader2 className="h-4 w-4 animate-spin" />\n'
    '                            <span>Waiting for model...</span>\n'
    '                        </div>\n'
    '                    ) : state === "started" || state === "streaming" ? (\n'
    '                        <div className="flex items-center gap-2 text-sm text-muted-foreground">\n'
    '                            <Loader2 className="h-4 w-4 animate-spin" />\n'
    '                            <span>Model is reasoning…</span>\n'
    '                        </div>\n'
    '                    ) : (\n'
    '                        <span className="italic text-muted-foreground">No response received.</span>\n'
    '                    )}\n',
    'model card reasoning empty state',
)
write(rel, text)


# ---------------------------------------------------------------------------
# Playwright: actual WebKit plus small/large mobile breakpoints.
# ---------------------------------------------------------------------------
rel = 'playwright.config.ts'
text = read(rel)
text = replace_once(
    text,
    "        viewport: { width: 390, height: 844 },\n        isMobile: true,\n",
    "        browserName: 'chromium',\n        viewport: { width: 390, height: 844 },\n        isMobile: true,\n",
    'playwright mobile chrome browser',
)
text = replace_once(
    text,
    "        viewport: { width: 375, height: 667 },\n        isMobile: true,\n",
    "        browserName: 'webkit',\n        viewport: { width: 375, height: 667 },\n        isMobile: true,\n",
    'playwright actual webkit',
)
text = replace_once(
    text,
    "    {\n      name: 'mobile-safari',\n      use: {\n        browserName: 'webkit',\n        viewport: { width: 375, height: 667 },\n        isMobile: true,\n        hasTouch: true,\n        storageState: 'apps/web/.playwright/.auth/user.json',\n      },\n      dependencies: ['setup'],\n    },\n",
    "    {\n      name: 'mobile-safari',\n      use: {\n        browserName: 'webkit',\n        viewport: { width: 375, height: 667 },\n        isMobile: true,\n        hasTouch: true,\n        storageState: 'apps/web/.playwright/.auth/user.json',\n      },\n      dependencies: ['setup'],\n    },\n    {\n      name: 'mobile-small',\n      use: {\n        browserName: 'chromium',\n        viewport: { width: 320, height: 568 },\n        isMobile: true,\n        hasTouch: true,\n        storageState: 'apps/web/.playwright/.auth/user.json',\n      },\n      dependencies: ['setup'],\n    },\n    {\n      name: 'mobile-large',\n      use: {\n        browserName: 'chromium',\n        viewport: { width: 430, height: 932 },\n        isMobile: true,\n        hasTouch: true,\n        storageState: 'apps/web/.playwright/.auth/user.json',\n      },\n      dependencies: ['setup'],\n    },\n",
    'playwright breakpoint projects',
)
write(rel, text)


# ---------------------------------------------------------------------------
# Regression tests.
# ---------------------------------------------------------------------------
rel = 'apps/api/tests/test_arena_pipeline_hardening.py'
text = read(rel)
text += '''\n\ndef test_user_scoped_failures_do_not_mutate_shared_circuit():\n    from model_gateway.provider_health import record_failure, record_success\n\n    with patch("model_gateway.provider_health.get_redis") as mock_get_redis:\n        redis = MagicMock()\n        mock_get_redis.return_value = redis\n\n        record_failure(\n            "openai",\n            "invalid_credentials",\n            "bad user key",\n            canonical_model_id="openai_fast",\n            credential_scope="user",\n        )\n        record_success(\n            "openai",\n            canonical_model_id="openai_fast",\n            credential_scope="user",\n        )\n\n        redis.set.assert_not_called()\n        redis.incr.assert_not_called()\n        redis.pipeline.assert_not_called()\n\n\ndef test_server_scoped_invalid_credentials_still_trip_global_circuit():\n    from model_gateway.provider_health import get_global_status_key, record_failure\n\n    with patch("model_gateway.provider_health.get_redis") as mock_get_redis:\n        redis = MagicMock()\n        mock_get_redis.return_value = redis\n\n        record_failure(\n            "openai",\n            "invalid_credentials",\n            "bad hosted key",\n            canonical_model_id="openai_fast",\n            credential_scope="server",\n        )\n\n        redis.set.assert_called_once_with(\n            get_global_status_key("openai"),\n            "open",\n            ex=3600,\n        )\n'''
write(rel, text)

rel = 'apps/web/lib/workspace/streamReducer.test.ts'
text = read(rel)
text += '''\n\ndescribe("streamingReducer lifecycle ordering", () => {\n  test("does not regress a streaming response to replayed queued state", () => {\n    const streaming = streamingReducer(INITIAL_STREAMING_STATE, delta("hello", 1));\n    const replayed = streamingReducer(streaming, {\n      type: "RESPONSE_QUEUED",\n      payload: { response_id: "response-1", model_id: "model-1" },\n    });\n\n    expect(replayed.buffers.get("response-1")?.state).toBe("streaming");\n    expect(replayed.buffers.get("response-1")?.accumulatedText).toBe("hello");\n  });\n\n  test("keeps completed state sticky when older lifecycle events replay", () => {\n    const streaming = streamingReducer(INITIAL_STREAMING_STATE, delta("done", 1));\n    const completed = streamingReducer(streaming, {\n      type: "RESPONSE_COMPLETED",\n      payload: { response_id: "response-1", model_id: "model-1" },\n    });\n    const replayed = streamingReducer(completed, {\n      type: "RESPONSE_STARTED",\n      payload: { response_id: "response-1", model_id: "model-1" },\n    });\n\n    expect(replayed.buffers.get("response-1")?.state).toBe("completed");\n    expect(replayed.buffers.get("response-1")?.accumulatedText).toBe("done");\n  });\n});\n'''
write(rel, text)

rel = 'apps/web/lib/workspace/synthesisReducer.test.ts'
path = ROOT / rel
if path.exists():
    text = read(rel)
else:
    text = 'import { describe, expect, test } from "vitest";\n\nimport { INITIAL_SYNTHESIS_STATE, synthesisReducer } from "./synthesisReducer";\n'
text += '''\n\ndescribe("synthesisReducer replay ordering", () => {\n  test("duplicate STARTED does not erase visible text", () => {\n    const started = synthesisReducer(INITIAL_SYNTHESIS_STATE, {\n      type: "STARTED",\n      payload: {\n        synthesis_id: "s1",\n        run_attempt: 1,\n        revision: 0,\n        status: "provisional",\n      },\n    });\n    const streamed = synthesisReducer(started, {\n      type: "DELTA",\n      payload: {\n        synthesis_id: "s1",\n        run_attempt: 1,\n        revision: 0,\n        status: "provisional",\n        text: "visible",\n        delta_sequence: 1,\n      },\n    });\n    const replayed = synthesisReducer(streamed, {\n      type: "STARTED",\n      payload: {\n        synthesis_id: "s1",\n        run_attempt: 1,\n        revision: 0,\n        status: "provisional",\n      },\n    });\n\n    expect(replayed.text).toBe("visible");\n    expect(replayed.status).toBe("streaming");\n  });\n});\n'''
write(rel, text)

print('C2-BUGFIX-21 patches applied successfully')
