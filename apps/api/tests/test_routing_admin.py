"""Test routing admin endpoints"""

from sqlmodel import Session, select


def test_routing_preview(authenticated_client, db_session: Session):
    # Create admin user
    from auth import COOKIE_NAME, create_access_token, hash_password
    from models import User
    
    admin_email = "admin@example.com"
    admin = db_session.exec(select(User).where(User.email == admin_email)).first()
    if not admin:
        admin = User(email=admin_email, password_hash=hash_password("password"), role="admin")
        db_session.add(admin)
        db_session.commit()
    
    # Login as admin
    access_token = create_access_token(user_id=admin.id, email=admin.email, role="admin")
    authenticated_client.cookies.set(COOKIE_NAME, access_token)
    
    # Test routing preview with default policy
    response = authenticated_client.get("/admin/routing/preview")
    assert response.status_code == 200
    data = response.json()
    
    assert "selected_model" in data
    assert "policy_used" in data
    assert "candidates" in data
    assert "context" in data
    
    assert data["policy_used"] == "router-smart"
    assert data["explicit_override"] is False
    assert len(data["candidates"]) > 0
    
    # Verify candidate structure
    candidate = data["candidates"][0]
    assert "model" in candidate
    assert "total_score" in candidate
    assert "cost_score" in candidate
    assert "latency_score" in candidate
    assert "quality_score" in candidate
    assert "safety_score" in candidate
    assert "is_healthy" in candidate


def test_routing_preview_with_explicit_model(authenticated_client, db_session: Session):
    # Create admin user
    from auth import COOKIE_NAME, create_access_token, hash_password
    from models import User
    
    admin_email = "admin@example.com"
    admin = db_session.exec(select(User).where(User.email == admin_email)).first()
    if not admin:
        admin = User(email=admin_email, password_hash=hash_password("password"), role="admin")
        db_session.add(admin)
        db_session.commit()
    
    # Login as admin
    access_token = create_access_token(user_id=admin.id, email=admin.email, role="admin")
    authenticated_client.cookies.set(COOKIE_NAME, access_token)
    
    # Test routing preview with explicit model
    response = authenticated_client.get("/admin/routing/preview?requested_model=gpt4o-mini")
    assert response.status_code == 200
    data = response.json()
    
    assert data["selected_model"] == "gpt4o-mini"
    assert data["explicit_override"] is True


def test_routing_preview_with_deep_policy(authenticated_client, db_session: Session):
    # Create admin user
    from auth import COOKIE_NAME, create_access_token, hash_password
    from models import User
    
    admin_email = "admin@example.com"
    admin = db_session.exec(select(User).where(User.email == admin_email)).first()
    if not admin:
        admin = User(email=admin_email, password_hash=hash_password("password"), role="admin")
        db_session.add(admin)
        db_session.commit()
    
    # Login as admin
    access_token = create_access_token(user_id=admin.id, email=admin.email, role="admin")
    authenticated_client.cookies.set(COOKIE_NAME, access_token)
    
    # Test routing preview with deep policy
    response = authenticated_client.get("/admin/routing/preview?routing_policy=router-deep")
    assert response.status_code == 200
    data = response.json()
    
    assert data["policy_used"] == "router-deep"
    # Deep policy prioritizes quality, so selected model should have high quality tier
    assert data["selected_model"] is not None


def test_admin_metrics_endpoint_authorization(authenticated_client, db_session: Session):
    # 1. As regular user (by default, authenticated_client is logged in as non-admin)
    # Let's verify that accessing /admin/metrics returns 403 Forbidden or 401 Unauthorized
    from auth import COOKIE_NAME, create_access_token, hash_password
    from models import User
    
    # Reset cookies to normal user
    normal_email = "normal-user-metrics@example.com"
    normal_user = db_session.exec(select(User).where(User.email == normal_email)).first()
    if not normal_user:
        normal_user = User(email=normal_email, password_hash=hash_password("password"), role="member")
        db_session.add(normal_user)
        db_session.commit()
        
    access_token = create_access_token(user_id=normal_user.id, email=normal_user.email, role="member")
    authenticated_client.cookies.set(COOKIE_NAME, access_token)
    
    response = authenticated_client.get("/admin/metrics")
    assert response.status_code in (401, 403)  # Forbidden or unauthorized for non-admin
    
    # 2. Login as admin and verify access
    admin_email = "admin-metrics-auth@example.com"
    admin = db_session.exec(select(User).where(User.email == admin_email)).first()
    if not admin:
        admin = User(email=admin_email, password_hash=hash_password("password"), role="admin", is_admin=True)
        db_session.add(admin)
        db_session.commit()
        
    admin_token = create_access_token(user_id=admin.id, email=admin.email, role="admin")
    authenticated_client.cookies.set(COOKIE_NAME, admin_token)
    
    response_admin = authenticated_client.get("/admin/metrics")
    assert response_admin.status_code == 200
    metrics = response_admin.json()
    assert "activation" in metrics
    assert "plg_sharing" in metrics
    assert "billing_conversion" in metrics
    assert "economics" in metrics

