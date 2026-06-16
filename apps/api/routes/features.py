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
        "conversation_mode": settings.ENABLE_CONVERSATION_MODE,
        "staged_decision_pipeline": getattr(settings, "STAGED_DECISION_PIPELINE", False),

        "llm_operation_limits": getattr(settings, "ENABLE_LLM_OPERATION_LIMITS", False),
        "prometheus_metrics": getattr(settings, "ENABLE_PROMETHEUS_METRICS", False),
        "otel_tracing": getattr(settings, "ENABLE_OTEL_TRACING", False),
        "gdpr_self_service": getattr(settings, "ENABLE_GDPR_SELF_SERVICE", False),

        "giphy": settings.ENABLE_GIPHY,
        "email_summaries": settings.ENABLE_EMAIL_SUMMARIES,
        "slack_alerts": settings.ENABLE_SLACK_ALERTS,

        "jit_auth": getattr(settings, "JIT_AUTH_ENABLED", False),
        "jitAuth": getattr(settings, "JIT_AUTH_ENABLED", False),

        "mobileReportV2": getattr(settings, "MOBILE_REPORT_V2", False),
        "mobile_report_v2": getattr(settings, "MOBILE_REPORT_V2", False),

        "github_sso": getattr(settings, "GITHUB_SSO_ENABLED", False),
        "google_sso": getattr(settings, "GOOGLE_SSO_ENABLED", False),
    }
