import logging
from typing import List

from .interfaces import DebateContext, DebatePipeline, DebateStage, DebateState
from .stages import CritiqueStage, DraftStage, JudgeStage, SynthesisStage
from .state import DebateStateManager

logger = logging.getLogger(__name__)


class StandardDebatePipeline(DebatePipeline):
    """
    The standard debate flow: Draft -> Critique -> Judge -> Synthesis.
    """
    def __init__(self, state_manager: DebateStateManager):
        self.stages: List[DebateStage] = [
            DraftStage(state_manager),
            CritiqueStage(state_manager),
            JudgeStage(state_manager),
            SynthesisStage(state_manager),
        ]

    async def execute(self, context: DebateContext) -> DebateState:
        from config import settings
        from database_async import async_session_scope
        from models import DebateAttempt
        from orchestration.execution_context import get_current_execution_lease
        from sqlmodel import select

        state = DebateState()

        # Resolve the current logical attempt once. Retry hydration must never
        # combine rows from multiple attempts. A completed upstream checkpoint
        # may intentionally reuse the most recent prior attempt, but invalidated
        # stages should see only current-attempt state and therefore rerun.
        current_attempt_id: str | None = self.stages[0].state_manager.attempt_id
        lease = get_current_execution_lease()
        current_attempt_number = int(lease.run_attempt) if lease is not None else 1
        if current_attempt_id is None:
            async with async_session_scope() as session:
                result = await session.execute(
                    select(DebateAttempt).where(
                        DebateAttempt.debate_id == context.debate_id,
                        DebateAttempt.attempt_number == current_attempt_number,
                    )
                )
                attempt = result.scalars().first()
                if attempt is not None:
                    current_attempt_id = attempt.id

        def _single_attempt_rows(rows, *, prefer_current: bool = True):
            """Return rows from exactly one attempt, never a cross-attempt mix.

            Current-attempt rows win. If a cache-hit upstream stage has no rows
            in the current attempt, select the newest prior attempt represented
            in the query result. Legacy NULL-attempt rows are a final fallback.
            """
            rows = list(rows)
            if not rows:
                return []
            if prefer_current and current_attempt_id:
                current = [row for row in rows if getattr(row, "attempt_id", None) == current_attempt_id]
                if current:
                    return current

            by_attempt: dict[str, list] = {}
            legacy: list = []
            for row in rows:
                attempt_id = getattr(row, "attempt_id", None)
                if attempt_id:
                    by_attempt.setdefault(str(attempt_id), []).append(row)
                else:
                    legacy.append(row)
            if by_attempt:
                # Rows are queried oldest->newest below; the attempt whose rows
                # contain the latest created item is the most recent source.
                selected = max(
                    by_attempt.values(),
                    key=lambda group: max(getattr(item, "created_at", None) for item in group),
                )
                return selected
            return legacy

        if context.is_resume:
            from models import Message

            # Preload only current-attempt rows. Falling back to a prior attempt
            # here would cause an explicitly invalidated Draft/Critique stage to
            # think it already ran and skip execution. Prior-attempt reuse is
            # performed only by run_with_checkpoint cache-hit load_fn below.
            async with async_session_scope() as session:
                stmt = select(Message).where(Message.debate_id == context.debate_id)
                if current_attempt_id:
                    stmt = stmt.where(Message.attempt_id == current_attempt_id)
                result = await session.execute(stmt)
                messages = result.scalars().all()

            candidates = []
            revised = []
            for msg in messages:
                if msg.role == "candidate":
                    candidates.append({
                        "persona": msg.persona,
                        "text": msg.content,
                        **(msg.meta or {})
                    })
                elif msg.role == "revised":
                    revised.append({
                        "persona": msg.persona,
                        "text": msg.content,
                        **(msg.meta or {})
                    })
            state.candidates = candidates
            state.revised_candidates = revised
            logger.info(
                "Resuming debate %s attempt=%s: loaded %d current candidates and %d current revised candidates",
                context.debate_id,
                current_attempt_number,
                len(candidates),
                len(revised),
            )

        from orchestration.checkpoints import run_with_checkpoint

        for stage in self.stages:
            logger.info("Debate %s: starting stage %s", context.debate_id, stage.name)

            if stage.name == "draft":
                input_data = {
                    "prompt": context.prompt,
                    "agents": [a.name for a in context.config.agents] if context.config else [],
                    "model_id": context.model_id
                }
            elif stage.name == "critique":
                input_data = {
                    "prompt": context.prompt,
                    "candidates": state.candidates,
                    "model_id": context.model_id
                }
            elif stage.name == "judge":
                input_data = {
                    "prompt": context.prompt,
                    "candidates": state.revised_candidates or state.candidates,
                    "judges": [j.name for j in context.config.judges] if context.config else [],
                    "model_id": context.model_id
                }
            elif stage.name == "synthesis":
                input_data = {
                    "prompt": context.prompt,
                    "candidates": state.revised_candidates or state.candidates,
                    "scores": state.scores,
                    "model_id": context.model_id
                }
            else:
                input_data = {"prompt": context.prompt}

            async def run_fn(s=stage, c=context, st=state):
                return await s.run(c, st)

            async def load_fn(session, s=stage, c=context, st=state):
                from models import Message, Score, Vote
                from sqlmodel import select

                if s.name == "draft":
                    result = await session.execute(
                        select(Message)
                        .where(Message.debate_id == c.debate_id)
                        .where(Message.role == "candidate")
                        .order_by(Message.created_at.asc(), Message.id.asc())
                    )
                    messages = _single_attempt_rows(result.scalars().all())
                    st.candidates = [{
                        "persona": msg.persona,
                        "text": msg.content,
                        **(msg.meta or {})
                    } for msg in messages]
                    st.round_index = 1

                elif s.name == "critique":
                    result = await session.execute(
                        select(Message)
                        .where(Message.debate_id == c.debate_id)
                        .where(Message.role == "revised")
                        .order_by(Message.created_at.asc(), Message.id.asc())
                    )
                    messages = _single_attempt_rows(result.scalars().all())
                    st.revised_candidates = [{
                        "persona": msg.persona,
                        "text": msg.content,
                        **(msg.meta or {})
                    } for msg in messages]
                    st.round_index = 2

                elif s.name == "judge":
                    score_result = await session.execute(
                        select(Score)
                        .where(Score.debate_id == c.debate_id)
                        .order_by(Score.created_at.asc(), Score.id.asc())
                    )
                    scores = _single_attempt_rows(score_result.scalars().all())
                    score_attempt_id = (
                        getattr(scores[0], "attempt_id", None) if scores else current_attempt_id
                    )

                    vote_result = await session.execute(
                        select(Vote)
                        .where(Vote.debate_id == c.debate_id)
                        .order_by(Vote.created_at.desc(), Vote.id.desc())
                    )
                    votes = list(vote_result.scalars().all())
                    vote = None
                    if score_attempt_id:
                        vote = next(
                            (
                                candidate
                                for candidate in votes
                                if isinstance(candidate.result, dict)
                                and candidate.result.get("_attempt_id") == score_attempt_id
                            ),
                            None,
                        )
                    # Legacy attempt-1 votes predate attempt markers. Use only
                    # as a fallback when no marked vote matches the selected
                    # source attempt; never merge multiple vote rows.
                    if vote is None and votes:
                        vote = next(
                            (
                                candidate
                                for candidate in votes
                                if not isinstance(candidate.result, dict)
                                or not candidate.result.get("_attempt_id")
                            ),
                            None,
                        )

                    aggregated = {}
                    for detail in scores:
                        persona_entry = aggregated.setdefault(
                            detail.persona,
                            {"persona": detail.persona, "scores": [], "rationale": detail.rationale},
                        )
                        persona_entry["scores"].append(detail.score)
                        persona_entry["rationale"] = detail.rationale
                    summary = []
                    for persona, payload in aggregated.items():
                        avg_score = sum(payload["scores"]) / max(1, len(payload["scores"]))
                        summary.append({
                            "persona": persona,
                            "score": round(avg_score, 2),
                            "rationale": payload["rationale"],
                        })
                    st.scores = summary
                    if vote:
                        st.ranking = vote.rankings.get("order") if vote.rankings else []
                        st.vote_details = {
                            key: value
                            for key, value in (vote.result or {}).items()
                            if key != "_attempt_id"
                        }
                    st.round_index = 3

                elif s.name == "synthesis":
                    result = await session.execute(
                        select(Message)
                        .where(Message.debate_id == c.debate_id)
                        .where(Message.role == "synthesizer")
                        .order_by(Message.created_at.desc(), Message.id.desc())
                    )
                    messages = _single_attempt_rows(result.scalars().all())
                    msg = messages[-1] if messages else None
                    if msg:
                        st.final_content = msg.content
                        if msg.meta and "synthesis_report" in msg.meta:
                            st.final_meta["synthesis_report"] = msg.meta["synthesis_report"]
                return st

            from sse_backend import get_sse_backend
            backend = get_sse_backend()
            round_map = {"draft": 1, "critique": 2, "judge": 3, "synthesis": 4}
            round_index = round_map.get(stage.name, 1)

            await backend.publish(
                context.channel_id,
                {
                    "type": "round_started",
                    "debate_id": context.debate_id,
                    "round": round_index,
                    "stage": stage.name,
                }
            )

            import time as time_module
            from observability.metrics import (
                record_pipeline_stage_duration,
                record_pipeline_stage_failure,
            )

            stage_mode = "recovery" if context.is_resume else "full"
            stage_start = time_module.monotonic()
            try:
                state = await run_with_checkpoint(
                    context.debate_id,
                    stage.name,
                    input_data,
                    run_fn,
                    load_fn,
                    owner_id=context.execution_owner_id,
                    lease_epoch=context.lease_epoch,
                )
                stage_elapsed = time_module.monotonic() - stage_start
                record_pipeline_stage_duration(stage.name, stage_mode, stage_elapsed)
            except Exception as exc:
                stage_elapsed = time_module.monotonic() - stage_start
                record_pipeline_stage_duration(stage.name, stage_mode, stage_elapsed)
                record_pipeline_stage_failure(stage.name, stage_mode)
                logger.error("Debate %s: stage %s failed: %s", context.debate_id, stage.name, exc)
                raise

            await backend.publish(
                context.channel_id,
                {
                    "type": "round_ended",
                    "debate_id": context.debate_id,
                    "round": round_index,
                    "stage": stage.name,
                }
            )

            if settings.STAGED_DECISION_PIPELINE and not context.is_resume and stage.name == "critique":
                logger.info(
                    "Debate %s: STAGED_DECISION_PIPELINE active. Pausing after critique stage.",
                    context.debate_id,
                )
                state.status = "perspectives_ready"
                return state

        state.status = "completed"
        return state
