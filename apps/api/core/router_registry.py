"""Central router registry for Consultaion API.

All domain routers are registered from this single source of truth.
Root routes serve as compatibility aliases; /api/v1 is the canonical namespace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from fastapi import APIRouter


@dataclass(frozen=True)
class RouterRegistration:
    """Defines how a domain router is mounted."""

    router: APIRouter
    root_enabled: bool = True
    v1_enabled: bool = True
    root_prefix: str | None = None
    v1_prefix: str | None = None
    tags: List[str] = field(default_factory=list)


def build_router_registry() -> List[RouterRegistration]:
    """Build the canonical list of all API routers.

    Import all domain routers here and return them in registration order.
    This eliminates the need to manually duplicate router includes across
    root and /api/v1 blocks.
    """
    from routes.auth import router as auth_router
    from routes.ops import router as ops_router
    from routes.stats import router as stats_router
    from routes.models import router as models_router
    from routes.debates import router as debates_router
    from routes.teams import router as teams_router
    from routes.admin import router as admin_router
    from routes.participation import router as participation_router
    from routes.arena import router as arena_router
    from routes.voting import router as voting_router
    from routes.redteam import router as redteam_router
    from routes.oracle import router as oracle_router
    from routes.challenge import router as challenge_router
    from routes.public_stats import router as public_stats_router
    from routes.routing_admin import router as routing_admin_router
    from billing.routes import billing_router
    from promotions.routes import promotions_router
    from routes.api_keys import api_keys_router
    from routes.provider_keys import router as provider_keys_router
    from routes.audit_logs import router as audit_logs_router
    from routes.features import router as features_router
    from routes.gifs import router as gifs_router
    from routes.votes import router as votes_router
    from gdpr.routes import gdpr_router

    return [
        RouterRegistration(auth_router),
        RouterRegistration(ops_router),
        RouterRegistration(stats_router),
        RouterRegistration(models_router),
        RouterRegistration(debates_router),
        RouterRegistration(teams_router),
        RouterRegistration(admin_router),
        RouterRegistration(participation_router),
        RouterRegistration(arena_router),
        RouterRegistration(voting_router),
        RouterRegistration(redteam_router),
        RouterRegistration(oracle_router),
        RouterRegistration(challenge_router),
        RouterRegistration(public_stats_router),
        RouterRegistration(routing_admin_router),
        RouterRegistration(billing_router),
        RouterRegistration(promotions_router),
        RouterRegistration(api_keys_router),
        RouterRegistration(provider_keys_router),
        RouterRegistration(audit_logs_router),
        RouterRegistration(features_router),
        RouterRegistration(gifs_router, root_prefix="/gifs", v1_prefix="/gifs", tags=["gifs"]),
        RouterRegistration(votes_router),
        RouterRegistration(gdpr_router),
    ]


def register_routers(app, settings) -> None:
    """Register all routers on the FastAPI app from the single registry.

    Root routes get a deprecation notice header.
    /api/v1 routes are the canonical namespace.
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    registry = build_router_registry()

    # Mount debug router separately (environment-gated)
    if settings.IS_LOCAL_ENV or settings.AUTH_DEBUG:
        from routes.debug import router as debug_router

        app.include_router(debug_router)
        v1_debug = APIRouter()
        v1_debug.include_router(debug_router)
    else:
        v1_debug = None

    for reg in registry:
        # Root routes (compatibility aliases)
        if reg.root_enabled:
            app.include_router(
                reg.router,
                prefix=reg.root_prefix or "",
            )

        # /api/v1 routes (canonical)
        if reg.v1_enabled:
            from fastapi import APIRouter as _APIRouter

            v1_ns = _APIRouter(prefix="/api/v1" + (reg.v1_prefix or ""))
            v1_ns.include_router(reg.router)
            app.include_router(v1_ns)

    # Mount debug router under v1 if enabled
    if v1_debug is not None:
        from fastapi import APIRouter as _APIRouter

        v1_debug_ns = _APIRouter(prefix="/api/v1")
        v1_debug_ns.include_router(v1_debug)
        app.include_router(v1_debug_ns)
