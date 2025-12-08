from config import settings
from fastapi import APIRouter

router = APIRouter(prefix="/features", tags=["features"])

@router.get("")
def get_feature_flags():
    """
    Returns the current status of feature flags.
    Frontend can use this to hide/show UI elements.
    """
    return {
        "conversation_mode": settings.ENABLE_CONVERSATION_MODE,
        "giphy": settings.ENABLE_GIPHY,
        "email_summaries": settings.ENABLE_EMAIL_SUMMARIES,
        "slack_alerts": settings.ENABLE_SLACK_ALERTS,
    }
