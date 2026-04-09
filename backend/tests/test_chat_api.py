"""Tests for chat API endpoint structure (not live Claude calls)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_chat_stream_endpoint_exists() -> None:
    """Verify the endpoint is registered and rejects bad input."""
    response = client.post("/api/chat/stream", json={})
    # Should get 422 (validation error for missing 'message') not 404
    assert response.status_code == 422


def test_chat_session_endpoint() -> None:
    """Verify session endpoint returns error for unknown session."""
    response = client.get("/api/chat/session/nonexistent")
    assert response.status_code == 200
    assert response.json() == {"error": "Session not found"}
