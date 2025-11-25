"""
API Key management routes.

Provides endpoints for creating, listing, and revoking API keys.

Patchset 37.0
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from api_key_utils import generate_api_key
from auth import get_current_user
from audit import record_audit
from deps import get_session
from exceptions import NotFoundError, PermissionError, ValidationError
from models import APIKey, User


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
        raise ValidationError(message="Key name is required", code="api_key.name_required")
    
    # TODO: Validate team_id if provided and check membership
    # For now, we'll just accept it
    
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
    
    record_audit(
        "api_key_created",
        user_id=current_user.id,
        target_type="api_key",
        target_id=api_key.id,
        meta={"name": api_key.name, "prefix": prefix},
        session=session,
    )
    
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
        raise ValidationError(message="Key already revoked", code="api_key.already_revoked")
    
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
