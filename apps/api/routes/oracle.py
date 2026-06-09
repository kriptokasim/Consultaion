from __future__ import annotations

import logging

from auth import get_current_user
from deps import get_session
from exceptions import NotFoundError, PermissionError
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from guards.llm_action_guard import require_llm_action_allowed
from models import OracleBranch, OracleSession, User, UserInteraction
from orchestration.oracle import generate_reasoning_chain
from pydantic import BaseModel, Field
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oracle", tags=["oracle"])

class OracleCreate(BaseModel):
    prompt: str = Field(..., min_length=5, description="The query to analyze")

class OracleFork(BaseModel):
    parent_branch_id: str = Field(..., description="The ID of the parent branch to fork from")
    fork_node_id: str = Field(..., description="The node ID in the parent branch after which to fork")
    assumption_text: str = Field(..., min_length=3, description="The custom counter-assumption or text to inject at the fork point")


async def run_base_reasoning_task(session_id: str, branch_id: str, prompt: str):
    try:
        from database_async import async_session_scope
        from sqlmodel import select
        
        # Generate nodes
        nodes = await generate_reasoning_chain(prompt)
        
        async with async_session_scope() as db_session:
            # Update branch reasoning nodes
            stmt = select(OracleBranch).where(OracleBranch.id == branch_id)
            res = await db_session.execute(stmt)
            branch = res.scalars().first()
            if branch:
                branch.reasoning_nodes = {"nodes": nodes}
                db_session.add(branch)

            # Update session status
            stmt_sess = select(OracleSession).where(OracleSession.id == session_id)
            res_sess = await db_session.execute(stmt_sess)
            session = res_sess.scalars().first()
            if session:
                session.status = "completed"
                db_session.add(session)

            await db_session.commit()
    except Exception as exc:
        logger.error(f"Failed background oracle reasoning: {exc}")
        try:
            from database_async import async_session_scope
            from sqlmodel import select as async_select
            async with async_session_scope() as db_session:
                stmt_sess = async_select(OracleSession).where(OracleSession.id == session_id)
                res_sess = await db_session.execute(stmt_sess)
                sess = res_sess.scalars().first()
                if sess:
                    sess.status = "failed"
                    db_session.add(sess)
                    await db_session.commit()
                stmt_branch = async_select(OracleBranch).where(OracleBranch.id == branch_id)
                res_branch = await db_session.execute(stmt_branch)
                br = res_branch.scalars().first()
                if br:
                    br.reasoning_nodes = {"error": "Analysis failed. Please retry."}
                    db_session.add(br)
                    await db_session.commit()
        except Exception:
            logger.error("Failed to persist oracle failure state for session %s", session_id)


async def run_fork_reasoning_task(
    session_id: str, 
    new_branch_id: str, 
    parent_branch_id: str, 
    fork_node_id: str, 
    assumption_text: str
):
    try:
        from database_async import async_session_scope
        from sqlmodel import select
        
        # Fetch parent branch nodes
        parent_nodes = []
        async with async_session_scope() as db_session:
            stmt = select(OracleBranch).where(OracleBranch.id == parent_branch_id)
            res = await db_session.execute(stmt)
            parent = res.scalars().first()
            if parent and parent.reasoning_nodes:
                parent_nodes = parent.reasoning_nodes.get("nodes", [])

        # Filter parent nodes up to fork_node_id (inclusive)
        prefix_nodes = []
        for node in parent_nodes:
            prefix_nodes.append(node)
            if node.get("id") == fork_node_id:
                break

        # Generate continuation nodes
        combined_nodes = await generate_reasoning_chain(
            prompt="", # Not used in fork path
            preceding_nodes=prefix_nodes,
            fork_assumption=assumption_text
        )

        async with async_session_scope() as db_session:
            stmt = select(OracleBranch).where(OracleBranch.id == new_branch_id)
            res = await db_session.execute(stmt)
            branch = res.scalars().first()
            if branch:
                branch.reasoning_nodes = {"nodes": combined_nodes}
                db_session.add(branch)

            # Mark session as completed
            stmt_sess = select(OracleSession).where(OracleSession.id == session_id)
            res_sess = await db_session.execute(stmt_sess)
            session = res_sess.scalars().first()
            if session:
                session.status = "completed"
                db_session.add(session)

            await db_session.commit()
    except Exception as exc:
        logger.error(f"Failed background oracle fork: {exc}")
        try:
            from database_async import async_session_scope
            from sqlmodel import select as async_select
            async with async_session_scope() as db_session:
                stmt_sess = async_select(OracleSession).where(OracleSession.id == session_id)
                res_sess = await db_session.execute(stmt_sess)
                sess = res_sess.scalars().first()
                if sess:
                    sess.status = "failed"
                    db_session.add(sess)
                    await db_session.commit()
                stmt_branch = async_select(OracleBranch).where(OracleBranch.id == new_branch_id)
                res_branch = await db_session.execute(stmt_branch)
                br = res_branch.scalars().first()
                if br:
                    br.reasoning_nodes = {"error": "Fork analysis failed. Please retry."}
                    db_session.add(br)
                    await db_session.commit()
        except Exception:
            logger.error("Failed to persist oracle fork failure state for session %s", session_id)


@router.post("")
async def start_oracle_session(
    payload: OracleCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    request: Request = None,
):
    """
    Initiates a user-facing reasoning summary session.
    """
    require_llm_action_allowed(
        user=current_user,
        action="oracle_session",
        session=session,
        ip_address=request.client.host if request.client else "0.0.0.0",
    )

    oracle_sess = OracleSession(
        user_id=current_user.id,
        prompt=payload.prompt,
        status="running"
    )
    session.add(oracle_sess)
    session.commit()
    session.refresh(oracle_sess)

    # Create initial root branch
    root_branch = OracleBranch(
        session_id=oracle_sess.id,
        parent_branch_id=None,
        assumption_text="Base reasoning summary",
        reasoning_nodes=None
    )
    session.add(root_branch)
    session.commit()
    session.refresh(root_branch)

    # Queue reasoning execution task
    background_tasks.add_task(
        run_base_reasoning_task,
        oracle_sess.id,
        root_branch.id,
        payload.prompt
    )

    return {
        "session_id": oracle_sess.id,
        "root_branch_id": root_branch.id,
        "prompt": oracle_sess.prompt,
        "status": "running",
        "created_at": oracle_sess.created_at
    }


@router.get("/{session_id}")
async def get_oracle_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Retrieves the Oracle session status and all associated reasoning branches.
    """
    oracle_sess = session.get(OracleSession, session_id)
    if not oracle_sess:
        raise NotFoundError(message="Oracle session not found", code="oracle.not_found")

    if not (current_user.role == "admin" or oracle_sess.user_id == current_user.id):
        raise PermissionError(message="Insufficient permissions", code="permission.denied")

    # Fetch all branches
    branches_res = session.exec(
        select(OracleBranch).where(OracleBranch.session_id == session_id)
    ).all()

    branches = []
    for b in branches_res:
        branches.append({
            "id": b.id,
            "parent_branch_id": b.parent_branch_id,
            "assumption_text": b.assumption_text,
            "nodes": b.reasoning_nodes.get("nodes", []) if b.reasoning_nodes else [],
            "created_at": b.created_at
        })

    return {
        "id": oracle_sess.id,
        "prompt": oracle_sess.prompt,
        "status": oracle_sess.status,
        "branches": branches,
        "created_at": oracle_sess.created_at
    }


@router.post("/{session_id}/fork")
async def fork_oracle_branch(
    session_id: str,
    payload: OracleFork,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    request: Request = None,
):
    """
    Forks the analysis from a specific node in a parent branch using a new counter-assumption.
    """
    oracle_sess = session.get(OracleSession, session_id)
    if not oracle_sess:
        raise NotFoundError(message="Oracle session not found", code="oracle.not_found")

    if not (current_user.role == "admin" or oracle_sess.user_id == current_user.id):
        raise PermissionError(message="Insufficient permissions", code="permission.denied")

    require_llm_action_allowed(
        user=current_user,
        action="oracle_fork",
        session=session,
        ip_address=request.client.host if request.client else "0.0.0.0",
    )

    # Verify parent branch exists
    parent = session.get(OracleBranch, payload.parent_branch_id)
    if not parent or parent.session_id != session_id:
        raise NotFoundError(message="Parent branch not found", code="oracle.parent_branch_not_found")

    # Set session status back to running while generating
    oracle_sess.status = "running"
    session.add(oracle_sess)

    # Create new child branch
    child_branch = OracleBranch(
        session_id=session_id,
        parent_branch_id=payload.parent_branch_id,
        assumption_text=payload.assumption_text,
        reasoning_nodes=None
    )
    session.add(child_branch)
    session.commit()
    session.refresh(child_branch)

    # Log interaction for participation tracking
    interaction = UserInteraction(
        user_id=current_user.id,
        interaction_type="oracle_branch",
        details={
            "entity_id": child_branch.id,
            "label": "fork",
            "summary": payload.assumption_text[:200],
            "status": "created"
        }
    )
    session.add(interaction)
    session.commit()

    # Queue fork reasoning generation task
    background_tasks.add_task(
        run_fork_reasoning_task,
        session_id,
        child_branch.id,
        payload.parent_branch_id,
        payload.fork_node_id,
        payload.assumption_text
    )

    return {
        "session_id": session_id,
        "forked_branch_id": child_branch.id,
        "status": "running",
        "created_at": child_branch.created_at
    }

# Alias for router inclusion
oracle_router = router
