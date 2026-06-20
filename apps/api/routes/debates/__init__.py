from fastapi import APIRouter
from models import Debate, Message, PairwiseVote, Score  # re-export for backward compat

from routes.debates.config_routes import (
    get_default_config,
    get_leaderboard,
    get_leaderboard_persona,
    router as _config_router,
)
from routes.debates.crud import (
    create_debate,
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
    retry_agent,
    retry_debate_run,
    router as _execution_router,
    start_debate_run,
)
from routes.debates.exports import export_debate_report, router as _exports_router
from routes.debates.moderation import (
    get_argument_tree,
    moderate_debate,
    router as _moderation_router,
    share_debate,
)
from routes.debates.schemas import (
    ContinuationResolveRequest,
    DebateListResponse,
    DebateModerateRequest,
    DebateShare,
    DebateUpdate,
    RetryAgentRequest,
    RetryRequest,
)
from routes.debates.streaming import (
    export_scores_csv,
    get_debate_events,
    get_debate_judges,
    get_debate_responses,
    replay_events,
    router as _streaming_router,
    stream_events,
)

router = APIRouter(tags=["debates"])

router.include_router(_config_router)
router.include_router(_crud_router)
router.include_router(_execution_router)
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
