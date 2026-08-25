from divergence_guard import install_divergence_guard
from fastapi import APIRouter
from models import Debate, Message, PairwiseVote, Score  # re-export for backward compat
from parliament_budget_guard import install_parliament_budget_guard
from sse_terminal_guard import install_terminal_commit_guard
from state_terminal_guard import install_terminal_accounting_guard
from structured_judge_guard import install_structured_judge_guard

from routes.debates.config_routes import (
    get_default_config,
    get_leaderboard,
    get_leaderboard_persona,
    router as _config_router,
)
from routes.debates.crud import (
    get_debate,
    get_debate_report,
    get_debate_timeline,
    list_debates,
    router as _crud_router,
    update_debate,
)
from routes.debates.dependencies import _champion_for_debate, _members_from_config
from routes.debates.execution import (
    continue_debate_run,
    get_debate_continuation,
    resolve_continuation_by_key,
    router as _execution_router,
    start_debate_run,
)
from routes.debates.exports import export_debate_report, router as _exports_router

# Install cross-cutting guards before the hardened router captures the legacy
# create callable. The judge guard rewrites that callable in-place.
install_structured_judge_guard()
install_parliament_budget_guard()
install_terminal_accounting_guard()
install_terminal_commit_guard()
install_divergence_guard()

from routes.debates.hardening import (  # noqa: E402
    create_debate_hardened as create_debate,
    retry_agent_hardened as retry_agent,
    retry_debate_run_hardened as retry_debate_run,
    router as _hardening_router,
)
from routes.debates.moderation import (  # noqa: E402
    get_argument_tree,
    moderate_debate,
    router as _moderation_router,
    share_debate,
)
from routes.debates.schemas import (  # noqa: E402
    ContinuationResolveRequest,
    DebateListResponse,
    DebateModerateRequest,
    DebateShare,
    DebateUpdate,
    RetryAgentRequest,
    RetryRequest,
)
from routes.debates.streaming import (  # noqa: E402
    export_scores_csv,
    get_debate_events,
    get_debate_judges,
    get_debate_responses,
    replay_events,
    router as _streaming_router,
    stream_events,
)


def _drop_post_route(source_router: APIRouter, path: str) -> None:
    """Remove superseded handlers before composing the public debate router."""
    source_router.routes[:] = [
        route
        for route in source_router.routes
        if not (
            getattr(route, "path", None) == path
            and "POST" in (getattr(route, "methods", None) or set())
        )
    ]


# Legacy modules remain importable for internal compatibility, but these three
# product mutations have a single hardened runtime authority.
_drop_post_route(_crud_router, "/debates")
_drop_post_route(_execution_router, "/debates/{debate_id}/retry")
_drop_post_route(_execution_router, "/debates/{debate_id}/retry-agent")

router = APIRouter(tags=["debates"])
router.include_router(_config_router)
router.include_router(_crud_router)
router.include_router(_execution_router)
router.include_router(_hardening_router)
router.include_router(_streaming_router)
router.include_router(_exports_router)
router.include_router(_moderation_router)

debates_router = router

__all__ = [
    "router",
    "debates_router",
    "Debate",
    "Message",
    "PairwiseVote",
    "Score",
    "get_default_config",
    "get_leaderboard",
    "get_leaderboard_persona",
    "create_debate",
    "get_debate",
    "get_debate_report",
    "get_debate_timeline",
    "list_debates",
    "update_debate",
    "_champion_for_debate",
    "_members_from_config",
    "continue_debate_run",
    "get_debate_continuation",
    "resolve_continuation_by_key",
    "retry_agent",
    "retry_debate_run",
    "start_debate_run",
    "export_debate_report",
    "get_argument_tree",
    "moderate_debate",
    "share_debate",
    "export_scores_csv",
    "get_debate_events",
    "get_debate_judges",
    "get_debate_responses",
    "replay_events",
    "stream_events",
    "ContinuationResolveRequest",
    "DebateListResponse",
    "DebateModerateRequest",
    "DebateShare",
    "DebateUpdate",
    "RetryAgentRequest",
    "RetryRequest",
]
