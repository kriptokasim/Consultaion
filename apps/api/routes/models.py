from fastapi import APIRouter
from parliament.model_registry import get_default_model, list_enabled_models
from schemas import ModelPublic

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/", summary="List enabled models", response_model=dict[str, list[ModelPublic]])
async def list_models():
    models = list_enabled_models()
    return {
        "models": [
            ModelPublic(
                id=cfg.id,
                display_name=cfg.display_name,
                provider=cfg.provider,  # Direct string, not enum
                capabilities=sorted(list(cfg.capabilities)),  # Convert set to list
                tier=cfg.tier,
                cost_tier=cfg.cost_tier,
                latency_class=cfg.latency_class,
                quality_tier=cfg.quality_tier,
                safety_profile=cfg.safety_profile,
                recommended=cfg.recommended,
                enabled=cfg.enabled,
                tags=cfg.tags,  # Optional field
            )
            for cfg in models
        ]
    }


@router.get("/default", summary="Get default model", response_model=ModelPublic)
async def default_model():
    cfg = get_default_model()
    return ModelPublic(
        id=cfg.id,
        display_name=cfg.display_name,
        provider=cfg.provider,
        capabilities=sorted(list(cfg.capabilities)),
        tier=cfg.tier,
        cost_tier=cfg.cost_tier,
        latency_class=cfg.latency_class,
        quality_tier=cfg.quality_tier,
        safety_profile=cfg.safety_profile,
        recommended=cfg.recommended,
        enabled=cfg.enabled,
        tags=cfg.tags,
    )


models_router = router
