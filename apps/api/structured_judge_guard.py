from __future__ import annotations

from typing import Any

from exceptions import ProviderCircuitOpenError, ValidationError
from parliament.model_registry import list_enabled_models_for_user, resolve_model_info
from schemas import DebateMode, default_debate_config, default_judges

_installed = False


def install_structured_judge_guard() -> None:
    """Normalize judge templates to executable models before debate creation."""
    global _installed
    if _installed:
        return

    from routes.debates import crud

    original = crud.create_debate

    async def guarded_create(*args: Any, **kwargs: Any):
        body = kwargs.get("body") if "body" in kwargs else (args[0] if args else None)
        current_user = kwargs.get("current_user")
        session = kwargs.get("session")
        if (
            body is not None
            and body.mode == DebateMode.debate
            and current_user is not None
            and session is not None
        ):
            from billing.service import get_active_plan

            enabled = {m.id: m for m in list_enabled_models_for_user(current_user.id)}
            plan = get_active_plan(session, current_user.id)
            allowed_tiers = (plan.limits or {}).get("allowed_model_tiers")
            if allowed_tiers is None:
                allowed_tiers = ["standard"] if plan.is_default_free else ["standard", "advanced"]
            allowed_tiers = set(allowed_tiers)
            eligible = [m for m in enabled.values() if getattr(m, "tier", "standard") in allowed_tiers]
            if not eligible:
                raise ProviderCircuitOpenError(
                    message="No judge models are available for Structured Debate.",
                    code="models.unavailable",
                    hint="Configure a provider or select another model.",
                )

            config = body.config or default_debate_config()
            explicit_judges = bool(body.config and body.config.judges)
            templates = list(config.judges or default_judges())
            normalized = []
            for index, judge in enumerate(templates):
                selected = None
                if judge.model:
                    info = resolve_model_info(judge.model)
                    if info is not None and info.id in enabled:
                        if getattr(info, "tier", "standard") in allowed_tiers:
                            selected = info
                        elif explicit_judges:
                            raise ValidationError(
                                message=f"Judge model '{info.display_name}' is not available on your plan.",
                                code="debate.model_tier_restricted",
                                hint="Select a judge model available on your plan.",
                            )
                    elif explicit_judges:
                        raise ValidationError(
                            message=f"Judge model '{judge.model}' is invalid or unavailable.",
                            code="debate.invalid_model",
                            hint="Select a currently available judge model.",
                        )

                if selected is None:
                    selected = eligible[index % len(eligible)]
                normalized.append(judge.model_copy(update={"model": selected.id}))

            body = body.model_copy(
                update={"config": config.model_copy(update={"judges": normalized})}
            )
            if "body" in kwargs:
                kwargs["body"] = body
            else:
                args = (body, *args[1:])

        return await original(*args, **kwargs)

    crud.create_debate = guarded_create
    _installed = True
