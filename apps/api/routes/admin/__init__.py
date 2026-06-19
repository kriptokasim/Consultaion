from __future__ import annotations

from fastapi import APIRouter

from routes.admin.alerts import admin_test_alert, router as alerts_router, update_ratings_endpoint
from routes.admin.logs import admin_events, admin_logs, router as logs_router
from routes.admin.metrics import admin_metrics, router as metrics_router
from routes.admin.models import admin_models, router as models_router
from routes.admin.operations import admin_ops_summary, admin_purge_old_data, router as operations_router
from routes.admin.promotions import admin_promotions, router as promotions_router
from routes.admin.providers import admin_providers_health, admin_test_provider, router as providers_router
from routes.admin.usage import admin_quota_usage, admin_usage_overview, router as usage_router
from routes.admin.users import (
    UpdateUserStatusRequest,
    admin_create_user_note,
    admin_get_user_notes,
    admin_search_users,
    admin_update_user_status,
    admin_user_billing,
    admin_user_detail,
    admin_user_summary,
    admin_users,
    change_user_plan,
    router as users_router,
)

router = APIRouter(prefix="/admin", tags=["admin"])

router.include_router(users_router)
router.include_router(usage_router)
router.include_router(operations_router)
router.include_router(models_router)
router.include_router(promotions_router)
router.include_router(logs_router)
router.include_router(providers_router)
router.include_router(metrics_router)
router.include_router(alerts_router)

admin_router = router
