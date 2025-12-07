"""
Tests for /models API endpoint.

Verifies that the /models endpoint returns stable JSON without 500 errors
and that the payload structure matches the ModelPublic schema.

Patchset 52.0
"""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("COOKIE_SECURE", "0")

sys.path.append(str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client():
    """Test client for making API requests."""
    from main import app
    return TestClient(app)


def test_models_returns_200_and_non_empty_list(client):
    """Test that /models endpoint returns 200 and a non-empty list."""
    response = client.get("/models")
    
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert isinstance(data["models"], list)
    assert len(data["models"]) > 0


def test_models_payload_has_required_fields(client):
    """Test that /models payload has all required fields from ModelPublic schema."""
    response = client.get("/models")
    
    assert response.status_code == 200
    data = response.json()
    models = data["models"]
    
    # Check first model has all required fields
    first_model = models[0]
    required_fields = [
        "id",
        "display_name",
        "provider",
        "capabilities",
        "tier",
        "cost_tier",
        "latency_class",
        "quality_tier",
        "safety_profile",
        "recommended",
        "enabled",
    ]
    
    for field in required_fields:
        assert field in first_model, f"Missing required field: {field}"
    
    # Verify types
    assert isinstance(first_model["id"], str)
    assert isinstance(first_model["display_name"], str)
    assert isinstance(first_model["provider"], str)
    assert isinstance(first_model["capabilities"], list)
    assert isinstance(first_model["tier"], str)
    assert isinstance(first_model["cost_tier"], str)
    assert isinstance(first_model["latency_class"], str)
    assert isinstance(first_model["quality_tier"], str)
    assert isinstance(first_model["safety_profile"], str)
    assert isinstance(first_model["recommended"], bool)
    assert isinstance(first_model["enabled"], bool)
    
    # Optional field 'tags' may be None or list
    if "tags" in first_model and first_model["tags"] is not None:
        assert isinstance(first_model["tags"], list)


def test_default_model_endpoint(client):
    """Test that /models/default endpoint returns a valid model."""
    response = client.get("/models/default")
    
    assert response.status_code == 200
    model = response.json()
    
    # Check required fields
    assert "id" in model
    assert "display_name" in model
    assert "provider" in model
    assert "capabilities" in model
    assert "tier" in model
    assert "recommended" in model
    
    # Verify types
    assert isinstance(model["id"], str)
    assert isinstance(model["capabilities"], list)
    assert isinstance(model["provider"], str)


def test_models_capabilities_is_list_not_set(client):
    """Test that capabilities field is a list (converted from set)."""
    response = client.get("/models")
    
    assert response.status_code == 200
    data = response.json()
    models = data["models"]
    
    for model in models:
        assert isinstance(model["capabilities"], list)
        # Should be sorted and unique (from set conversion)
        if len(model["capabilities"]) > 1:
            assert model["capabilities"] == sorted(model["capabilities"])
