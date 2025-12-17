
import logging

from fastapi.testclient import TestClient
from main import app


def test_request_id_propagation_in_logs(client: TestClient, caplog):
    # Enable info logging
    caplog.set_level(logging.INFO, logger="apps")
    
    # Hit an endpoint that logs.
    # /auth/login with invalid creds logs a warning or error handled by exception handler?
    # Or /healthz
    # Let's hit a non-existent endpoint to trigger 404 handler or general request logging if enabled?
    # Our middleware setup: 
    # LogConfig sets up filters.
    # But usually access logs are uvicorn.access.
    # We want "apps" logger.
    
    # Check "auth.py" logs?
    # It logs [AUTH_DEBUG] if enabled.
    
    # Or force an error that logs.
    # Or use a fake route.
    
    from fastapi import APIRouter
    from log_config import get_request_id
    
    # Temporarily add a route that logs
    router = APIRouter()
    @router.get("/test/log-id")
    def log_something():
        rid = get_request_id()
        return {"request_id": rid}
    
    app.include_router(router)
    
    response = client.get("/test/log-id")
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] != "-"
    assert len(data["request_id"]) > 0
    # Ideally check if it's a UUID or whatever format we generate

