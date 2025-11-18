from fastapi import APIRouter

from model_registry import get_default_model, list_enabled_models
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
                provider=cfg.provider.value,
                tags=cfg.tags,
                max_context=cfg.max_context,
                recommended=cfg.recommended,
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
        provider=cfg.provider.value,
        tags=cfg.tags,
        max_context=cfg.max_context,
        recommended=cfg.recommended,
    )


models_router = router
