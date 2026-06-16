from config import settings
from fastapi import APIRouter

router = APIRouter(prefix="/config/features", tags=["config"])

@router.get("")
def get_feature_flags():
    """
    Returns the current status of feature flags.
    Frontend can use this to hide/show UI elements.
    """
    return {
        # Pipeline & workspace flags
        "conversation_mode": settings.ENABLE_CONVERSATION_MODE,
        "staged_decision_pipeline": getattr(settings, "STAGED_DECISION_PIPELINE", False),

        # Operational trust flags
        "llm_operation_limits": getattr(settings, "ENABLE_LLM_OPERATION_LIMITS", False),
        "prometheus_metrics": getattr(settings, "ENABLE_PROMETHEUS_METRICS", False),
        "otel_tracing": getattr(settings, "ENABLE_OTEL_TRACING", False),
        "gdpr_self_service": getattr(settings, "ENABLE_GDPR_SELF_SERVICE", False),

        # Feature toggles
        "giphy": settings.ENABLE_GIPHY,
        "email_summaries": settings.ENABLE_EMAIL_SUMMARIES,
        "slack_alerts": settings.ENABLE_SLACK_ALERTS,
        "jit_auth": getattr(settings, "JIT_AUTH_ENABLED", False),

        # SSO / integration flags
        "github_sso": getattr(settings, "GITHUB_SSO_ENABLED", False),
        "google_sso": getattr(settings, "GOOGLE_SSO_ENABLED", False),
    }
