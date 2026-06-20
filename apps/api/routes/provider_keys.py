import logging
from datetime import datetime

import httpx
from auth import get_current_user
from deps import get_session
from exceptions import NotFoundError, ValidationError
from fastapi import APIRouter, Depends, HTTPException
from models import User, UserProviderKey, utcnow
from pydantic import BaseModel, Field
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/provider-keys", tags=["provider_keys"])


class ProviderKeySubmit(BaseModel):
    provider: str = Field(..., description="Provider name: openai, anthropic, gemini, openrouter")
    key: str = Field(..., description="The cleartext API key to validate and save")


class ProviderKeyValidate(BaseModel):
    provider: str = Field(..., description="Provider name: openai, anthropic, gemini, openrouter")
    key: str = Field(..., description="The cleartext API key to validate")


class ProviderKeyResponse(BaseModel):
    id: str
    provider: str
    masked_key: str
    created_at: datetime
    updated_at: datetime


async def validate_key_with_provider(provider: str, key: str) -> bool:
    """
    Validates the API key by sending a minimal request to the provider's API.
    Raises ValidationError if validation fails.
    """
    provider = provider.lower().strip()
    if not key or not key.strip():
        raise ValidationError(message="API key cannot be empty", code="provider_key.empty")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if provider == "openai":
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {key}"}
                )
                if response.status_code != 200:
                    logger.warning("OpenAI key validation failed: status=%d", response.status_code)
                    raise ValidationError(
                        message="OpenAI key validation failed. Please check your key.",
                        code="provider_key.validation_failed"
                    )
            elif provider == "anthropic":
                # Check models endpoint
                response = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01"
                    }
                )
                if response.status_code != 200:
                    logger.warning("Anthropic key validation failed: status=%d", response.status_code)
                    raise ValidationError(
                        message="Anthropic key validation failed. Please check your key.",
                        code="provider_key.validation_failed"
                    )
            elif provider == "gemini":
                # POST generate content
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}",
                    headers={"Content-Type": "application/json"},
                    json={"contents": [{"parts": [{"text": "Hello"}]}]}
                )
                if response.status_code != 200:
                    logger.warning("Gemini key validation failed: status=%d", response.status_code)
                    raise ValidationError(
                        message="Gemini key validation failed. Please check your key.",
                        code="provider_key.validation_failed"
                    )
            elif provider == "openrouter":
                response = await client.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {key}"}
                )
                if response.status_code != 200:
                    logger.warning("OpenRouter key validation failed: status=%d", response.status_code)
                    raise ValidationError(
                        message="OpenRouter key validation failed. Please check your key.",
                        code="provider_key.validation_failed"
                    )
            else:
                raise ValidationError(
                    message=f"Unsupported provider: {provider}",
                    code="provider_key.unsupported_provider"
                )
            return True
        except httpx.RequestError as e:
            logger.error(f"Network error during key validation for {provider}: {e}")
            raise ValidationError(
                message=f"Network error trying to contact {provider} API. Please try again later.",
                code="provider_key.network_error"
            ) from e


def mask_provider_key(provider: str, key: str) -> str:
    """Masks key for safe client display."""
    key = key.strip()
    if len(key) <= 8:
        return "****"
    
    # OpenAI/Anthropic/OpenRouter keys have prefixes
    if provider == "openai":
        return f"sk-...{key[-4:]}"
    elif provider == "anthropic":
        return f"sk-ant-...{key[-4:]}"
    else:
        return f"{key[:4]}...{key[-4:]}"


@router.get("", response_model=list[ProviderKeyResponse])
async def list_provider_keys(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all masked provider keys for the current user."""
    stmt = select(UserProviderKey).where(UserProviderKey.user_id == current_user.id)
    keys = session.exec(stmt).all()
    return keys


@router.post("", response_model=ProviderKeyResponse)
async def save_provider_key(
    body: ProviderKeySubmit,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Validate and save/update a provider key."""
    provider_name = body.provider.lower().strip()
    
    # 1. Validate the key with the remote API
    await validate_key_with_provider(provider_name, body.key)
    
    # 2. Check if key already exists for user + provider
    stmt = select(UserProviderKey).where(
        UserProviderKey.user_id == current_user.id,
        UserProviderKey.provider == provider_name
    )
    existing_key = session.exec(stmt).first()
    
    masked = mask_provider_key(provider_name, body.key)

    # FH125 D-2: Encrypt key at rest — fail closed in all environments
    try:
        from security.encryption import encrypt_value, fingerprint_key
        encrypted_payload = encrypt_value(
            body.key.strip(),
            user_id=current_user.id,
            provider=provider_name,
        )
        encrypted = encrypted_payload["ciphertext"]
        nonce = encrypted_payload["nonce"]
        key_version = encrypted_payload["key_version"]
        fingerprint = fingerprint_key(body.key.strip())
    except (RuntimeError, ImportError) as exc:
        # Never store plaintext — fail closed in all environments
        raise HTTPException(
            status_code=503,
            detail="Provider key encryption is not configured. Set PROVIDER_KEY_ENCRYPTION_KEY."
        ) from exc
    
    if existing_key:
        existing_key.masked_key = masked
        existing_key.encrypted_key = encrypted
        existing_key.encryption_nonce = nonce
        existing_key.encryption_key_version = key_version
        existing_key.key_fingerprint = fingerprint
        existing_key.updated_at = utcnow()
        session.add(existing_key)
        key_record = existing_key
    else:
        key_record = UserProviderKey(
            user_id=current_user.id,
            provider=provider_name,
            masked_key=masked,
            encrypted_key=encrypted,
            encryption_nonce=nonce,
            encryption_key_version=key_version,
            key_fingerprint=fingerprint,
            created_at=utcnow(),
            updated_at=utcnow()
        )
        session.add(key_record)
        
    session.commit()
    session.refresh(key_record)
    return key_record


@router.delete("/{provider}")
async def delete_provider_key(
    provider: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a provider key."""
    provider_name = provider.lower().strip()
    stmt = select(UserProviderKey).where(
        UserProviderKey.user_id == current_user.id,
        UserProviderKey.provider == provider_name
    )
    key_record = session.exec(stmt).first()
    
    if not key_record:
        raise NotFoundError(message=f"Key for provider {provider} not found", code="provider_key.not_found")
        
    session.delete(key_record)
    session.commit()
    return {"provider": provider_name, "deleted": True}


@router.post("/validate")
async def validate_only(
    body: ProviderKeyValidate,
    current_user: User = Depends(get_current_user),
):
    """Validate a provider key without saving it."""
    valid = await validate_key_with_provider(body.provider, body.key)
    return {"valid": valid}
