import pytest
from config import AppSettings
from pydantic import ValidationError


def test_cors_validation_local_allows_wildcard(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    settings = AppSettings()
    assert settings.CORS_ORIGINS == "*" or "*" in settings.CORS_ORIGINS

def test_cors_validation_prod_disallows_wildcard(monkeypatch):
    monkeypatch.setenv("ENV", "production") 
    monkeypatch.setenv("RENDER", "0") # ensure not local
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("JWT_SECRET", "a" * 32) 
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379") 
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test") # Required when verify=True (default)

    with pytest.raises(ValidationError) as excinfo:
        AppSettings()
    assert "Wildcard CORS origin '*' is not allowed" in str(excinfo.value)

def test_cors_validation_prod_allows_valid_origins(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("RENDER", "0")
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com,https://api.example.com")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    
    settings = AppSettings()
    assert "https://example.com" in settings.CORS_ORIGINS
