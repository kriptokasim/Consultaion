"""
Tests for team-scoped API key creation.

Verifies that team membership checks work correctly and that
only team members can create team-scoped API keys.

Patchset 52.0
"""

import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("COOKIE_SECURE", "0")

sys.path.append(str(Path(__file__).resolve().parents[1]))

import database  # noqa: E402
from auth import hash_password  # noqa: E402
from models import Team, TeamMember, User  # noqa: E402
from sqlmodel import Session, select  # noqa: E402


@pytest.fixture
def client():
    """Test client for making API requests."""
    from main import app
    return TestClient(app)


def test_team_api_key_creation_requires_membership(client):
    """Test that non-members cannot create team-scoped API keys."""
    with Session(database.engine) as session:
        # Create a team
        team_id = str(uuid.uuid4())
        team = Team(id=team_id, name="Test Team")
        session.add(team)
        session.commit()
        
        # Create a user who is NOT a member of the team
        non_member = User(
            id=str(uuid.uuid4()),
            email="nonmember@example.com",
            password_hash=hash_password("password123"),
            role="user",
        )
        session.add(non_member)
        session.commit()
        session.refresh(non_member)
    
    # Login as non-member
    login_response = client.post(
        "/auth/login",
        json={"email": "nonmember@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    
    # Attempt to create team-scoped API key
    response = client.post(
        "/keys",
        json={"name": "Team Key", "team_id": team_id}
    )
    
    # Should fail with permission error
    assert response.status_code == 403
    data = response.json()
    # API returns error in format: {"error": {"code": "...", "message": "...", "details": {...}}}
    assert "error" in data
    error = data["error"]
    assert error["code"] == "team.not_member"
    assert "not a member" in error["message"].lower()


def test_team_api_key_creation_succeeds_for_member(client, db_session):
    """Test that team members can create team-scoped API keys."""
    # Create a team
    team_id = str(uuid.uuid4())
    team = Team(id=team_id, name="Test Team For Members")
    db_session.add(team)
    db_session.commit()
    
    # Create a user
    member = User(
        id=str(uuid.uuid4()),
        email="member@example.com",
        password_hash=hash_password("password123"),
        role="user",
    )
    db_session.add(member)
    db_session.commit()
    db_session.refresh(member)
    
    # Add user as team member
    membership = TeamMember(
        user_id=member.id,
        team_id=team_id,
        role="editor",
    )
    db_session.add(membership)
    db_session.commit()
    
    # Login as member
    login_response = client.post(
        "/auth/login",
        json={"email": "member@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    
    # Create team-scoped API key
    response = client.post(
        "/keys",
        json={"name": "Team Key For Member", "team_id": team_id}
    )
    
    # Should succeed
    assert response.status_code == 200
    data = response.json()
    assert "secret" in data
    assert data["secret"].startswith("pk_")
    assert "id" in data
    
    # Verify key was created with correct team_id
    from models import APIKey
    stmt = select(APIKey).where(APIKey.id == data["id"])
    created_key = db_session.exec(stmt).first()
    
    assert created_key is not None
    assert created_key.team_id == team_id
    assert created_key.user_id == member.id
    assert created_key.revoked is False


def test_admin_can_create_team_api_keys(client):
    """Test that admin users can create team-scoped keys for any team."""
    with Session(database.engine) as session:
        # Create a team
        team_id = str(uuid.uuid4())
        team = Team(id=team_id, name="Admin Test Team")
        session.add(team)
        session.commit()
        
        # Create admin user (not explicitly a team member)
        admin = User(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            password_hash=hash_password("admin123"),
            role="admin",
        )
        session.add(admin)
        session.commit()
    
    # Login as admin
    login_response = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "admin123"}
    )
    assert login_response.status_code == 200
    
    # Admin should be able to create team-scoped key
    response = client.post(
        "/keys",
        json={"name": "Admin Team Key", "team_id": team_id}
    )
    
    # Should succeed for admin
    assert response.status_code == 200
    data = response.json()
    assert "secret" in data
