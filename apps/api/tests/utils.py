import os
import contextlib
from typing import Dict, Optional, Generator

from config import settings
from parliament.provider_health import reset_health_state, clear_all_health_states


@contextlib.contextmanager
def override_env(vars: Dict[str, Optional[str]]) -> Generator[None, None, None]:
    """
    Context manager to temporarily override environment variables.
    
    Args:
        vars: Dictionary of env vars to set. If value is None, the var is unset.
    """
    original = {}
    
    # Save original values and apply overrides
    for key, value in vars.items():
        original[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(value)
            
    try:
        yield
    finally:
        # Restore original values
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextlib.contextmanager
def settings_context(**overrides) -> Generator[None, None, None]:
    """
    Context manager to override settings via environment variables and reload.
    
    Usage:
        with settings_context(FAST_DEBATE="1", ENV="test"):
            assert settings.FAST_DEBATE is True
            
    Args:
        **overrides: Key-value pairs of settings to override.
    """
    # Convert all values to strings (or None) for env vars
    env_vars = {k: str(v) if v is not None else None for k, v in overrides.items()}
    
    with override_env(env_vars):
        settings.reload()
        try:
            yield
        finally:
            settings.reload()


def reset_provider_health(provider: Optional[str] = None, model: Optional[str] = None) -> None:
    """
    Reset provider health state.
    
    Args:
        provider: Optional provider name to reset specific state
        model: Optional model name to reset specific state
    """
    if provider and model:
        reset_health_state(provider, model)
    else:
        clear_all_health_states()
