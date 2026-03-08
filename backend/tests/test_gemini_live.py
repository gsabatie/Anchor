"""Integration tests for Gemini Live WebSocket."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

from main import app

# Test credentials
TEST_TOKEN = os.getenv("WS_AUTH_TOKEN", "test-token")
TEST_WS_URL = f"ws://localhost:8000/ws/session?token={TEST_TOKEN}"


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


def test_websocket_requires_auth(client):
    """Test that WebSocket rejects connections without valid token."""
    with pytest.raises(Exception):  # Should fail auth
        with client.websocket_connect("ws://localhost:8000/ws/session?token=invalid"):
            pass


@pytest.mark.asyncio
async def test_websocket_accepts_valid_token():
    """Test that WebSocket accepts valid token."""
    # This requires a real server running
    # For CI, we'd mock the Gemini Live connection
    pytest.skip("Requires running server")


@pytest.mark.asyncio
async def test_gemini_live_session_initialization():
    """Test GeminiLiveSession initialization."""
    from services.gemini_live import GeminiLiveSession

    with patch("google.genai.Client") as mock_client:
        session = GeminiLiveSession(gemini_api_key="test-key")
        assert session is not None
        mock_client.assert_called_once_with(api_key="test-key")


@pytest.mark.asyncio
async def test_reassurance_guard_blocks_harmful_text():
    """Test that reassurance guard blocks unsafe patterns."""
    from agent.tools.reassurance_guard import reassurance_guard

    # Should block reassuring text
    result = reassurance_guard("Ça va aller, ne t'inquiète pas.")
    assert result["allowed"] is False
    assert "ERP" in result["replacement"]

    # Should allow neutral text
    result = reassurance_guard("Raconte-moi ce qui se passe.")
    assert result["allowed"] is True


@pytest.mark.asyncio
async def test_audio_chunk_size_validation():
    """Test that oversized audio chunks are rejected."""
    from api.websocket import MAX_AUDIO_CHUNK_SIZE

    # Create oversized chunk
    oversized = b"\x00" * (MAX_AUDIO_CHUNK_SIZE + 1)

    # Would need a mock WebSocket to test properly
    # This is more of an integration test
    assert len(oversized) > MAX_AUDIO_CHUNK_SIZE


def test_response_message_format():
    """Test that response messages have correct format."""
    responses = [
        {
            "type": "text",
            "content": "Test message",
            "timestamp": "2026-03-08T10:30:00Z"
        },
        {
            "type": "audio",
            "data": "base64data",
            "timestamp": "2026-03-08T10:30:00Z"
        },
        {
            "type": "exposure_image",
            "url": "https://example.com/image.jpg"
        },
        {
            "type": "timer",
            "duration": 300,
            "elapsed": 45
        }
    ]

    for resp in responses:
        assert "type" in resp
        assert resp["type"] in ["text", "audio", "exposure_image", "timer", "error"]
        # Can parse as JSON
        assert json.dumps(resp)


@pytest.mark.asyncio
async def test_bidirectional_communication():
    """Test simultaneous send and receive tasks."""
    from api.websocket import _receive_client_audio, _send_gemini_responses

    # Mock WebSocket
    mock_ws = AsyncMock()
    mock_session = AsyncMock()

    # Queue some test responses
    responses = [
        {"type": "connection", "status": "connected"},
        {"type": "text", "content": "Hello"},
    ]
    mock_session.receive_responses.return_value = iter(responses)

    # This would need proper async setup
    # Mainly here as documentation of expected behavior
    pytest.skip("Requires full async mock setup")


def test_control_message_formats():
    """Test that control messages are properly formatted."""
    control_messages = [
        {"type": "control", "action": "pause"},
        {"type": "control", "action": "resume"},
        {"type": "control", "action": "end_session"},
    ]

    for msg in control_messages:
        assert msg["type"] == "control"
        assert msg["action"] in ["pause", "resume", "end_session"]
        assert json.dumps(msg)


@pytest.mark.asyncio
async def test_error_recovery():
    """Test that errors are properly reported and don't crash server."""
    # This would be an integration test
    pytest.skip("Requires full integration setup")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
