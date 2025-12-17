
from auth import CSRF_COOKIE_NAME, hash_password
from fastapi.testclient import TestClient
from models import User
from sqlmodel import Session


def test_retry_after_header_presence(client: TestClient, monkeypatch):
    # Enforce strict rate limit
    monkeypatch.setenv("RL_MAX_CALLS", "1")
    monkeypatch.setenv("RL_WINDOW", "60")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    
    # Reload config/ratelimit to pick up env change if needed
    import importlib

    import config
    import ratelimit
    config.settings.reload()
    importlib.reload(ratelimit)
    
    # Needs to reset backend
    ratelimit.reset_rate_limiter_backend_for_tests()
    
    # Make calls to a rate-limited endpoint (e.g. auth login)
    # Patch the imported constant in auth module directly
    import routes.auth
    monkeypatch.setattr(routes.auth, "AUTH_MAX_CALLS", 1)
    
    url = "/auth/login"
    payload = {"email": "test@example.com", "password": "password"}
    
    # First call - should succeed (or fail auth, but allow request)
    resp = client.post(url, json=payload)
    # Even if 401, it counts against rate limit if by IP?
    # increment_ip_bucket is called first.
    
    # Second call - should be 429
    resp = client.post(url, json=payload)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) > 0

def test_csrf_cookie_rotation(client: TestClient, db_session: Session, monkeypatch):
    # Enable CSRF
    monkeypatch.setenv("ENABLE_CSRF", "true")
    
    # Create user
    password = "StrongPassword123!"
    user = User(email="csrf_test@example.com", password_hash=hash_password(password), is_active=True)
    db_session.add(user)
    db_session.commit()
    
    # Login
    resp = client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    assert CSRF_COOKIE_NAME in resp.cookies
    token1 = resp.cookies[CSRF_COOKIE_NAME]
    assert len(token1) > 0

    # Logout
    resp = client.post("/auth/logout")
    assert resp.status_code == 200
    # Cookie should be cleared (empty or past expiry) using TestClient cookie jar logic
    # TestClient doesn't automatically expire cookies but delete_cookie removes it from jar?
    # Let's check headers or cookie jar.
    # If standard delete_cookie was called, value is empty string.
    
    # In requests/TestClient, deleted cookies might be removed or set to empty.
    # Let's verify we get a Set-Cookie header clearing it.
    assert "Set-Cookie" in resp.headers
    # Or checking cookies directly:
    # If using client.cookies (jar), it might be gone.
    assert CSRF_COOKIE_NAME not in client.cookies or client.cookies[CSRF_COOKIE_NAME] == ""
