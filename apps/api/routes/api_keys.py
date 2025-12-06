"""
API Key management routes.

Provides endpoints for creating, listing, and revoking API keys.

Patchset 37.0
"""

import logging
from datetime import datetime
from typing import Optional

from api_key_utils import generate_api_key
from audit import record_audit
from auth import get_current_user
from deps import get_session
from exceptions import NotFoundError, PermissionError, ValidationError
from fastapi import APIRouter, Depends
from models import APIKey, User
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

logger = logging.getLogger(__name__)


router = APIRouter(tags=["api_keys"])


class APIKeyCreate(BaseModel):
    name: str
    team_id: Optional[str] = None


class APIKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: datetime
    last_used_at: Optional[datetime]
    revoked: bool
    team_id: Optional[str]


class APIKeyCreateResponse(BaseModel):
    """Response for key creation - includes full secret once."""
    id: str
    name: str
    prefix: str
    created_at: datetime
    secret: str  # Full key, shown only once


@router.get("/keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    List all API keys for the current user.
    
    Returns keys owned by the user, excluding the full secret.
    """
    stmt = select(APIKey).where(
        APIKey.user_id == current_user.id
    ).order_by(APIKey.created_at.desc())
    
    keys = session.exec(stmt).all()
    
    return [
        APIKeyResponse(
            id=key.id,
            name=key.name,
            prefix=key.prefix,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            revoked=key.revoked,
            team_id=key.team_id,
        )
        for key in keys
    ]


@router.post("/keys", response_model=APIKeyCreateResponse)
async def create_api_key(
    body: APIKeyCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new API key.
    
    Returns the full secret exactly once. Store it securely!
    """
    if not body.name or not body.name.strip():
        raise ValidationError(
            message="Key name is required", 
            code="api_key.name_required",
            hint="Please provide a descriptive name for your API key."
        )
    
    
    # Validate team_id if provided - user must be a member of the team
    if body.team_id:
        from routes.common import user_is_team_member
        if not user_is_team_member(session, current_user.id, body.team_id):
            raise PermissionError(
                message="You are not a member of this team",
                code="team.not_member"
            )
    
    # Generate key
    full_key, prefix, hashed_key = generate_api_key()
    
    # Create database record
    api_key = APIKey(
        user_id=current_user.id,
        team_id=body.team_id,
        name=body.name.strip(),
        prefix=prefix,
        hashed_key=hashed_key,
        revoked=False,
    )
    
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    
    try:
        record_audit(
            "api_key_created",
            user_id=current_user.id,
            target_type="api_key",
            target_id=api_key.id,
            meta={"name": api_key.name, "prefix": prefix},
            session=session,
        )
    except SQLAlchemyError as e:
        logger.warning(f"Failed to write audit log for API key {api_key.id}: {e}")
        # Do not rollback the API key creation; it's already committed and valid.
        # Just swallow the error so the user gets their key.
    
    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        created_at=api_key.created_at,
        secret=full_key,  # Only time we return this!
    )


@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Revoke an API key.
    
    Once revoked, the key can no longer be used for authentication.
    """
    api_key = session.get(APIKey, key_id)
    
    if not api_key:
        raise NotFoundError(message="API key not found", code="api_key.not_found")
    
    # Only owner can revoke
    if api_key.user_id != current_user.id:
        raise PermissionError(message="Insufficient permissions", code="permission.denied")
    
    if api_key.revoked:
        raise ValidationError(
            message="Key already revoked", 
            code="api_key.already_revoked",
            hint="This key has already been revoked and cannot be used."
        )
    
    api_key.revoked = True
    session.add(api_key)
    session.commit()
    
    record_audit(
        "api_key_revoked",
        user_id=current_user.id,
        target_type="api_key",
        target_id=api_key.id,
        meta={"name": api_key.name, "prefix": api_key.prefix},
        session=session,
    )
    
    return {"id": key_id, "revoked": True}


# Alias for router inclusion
api_keys_router = router
