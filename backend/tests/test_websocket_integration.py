"""Integration tests for the WebSocket endpoint with mocked Gemini."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.helpers import TEST_TOKEN, make_pcm16_silence
from api.websocket import MAX_AUDIO_CHUNK_SIZE


def _make_mock_session_class(responses=None):
    """Build a mock GeminiLiveSession class that yields `responses`."""
    mock_instance = AsyncMock()
    mock_instance.connect = AsyncMock()
    mock_instance.disconnect = AsyncMock()
    mock_instance.send_audio = AsyncMock()
    mock_instance.send_text = AsyncMock()

    async def _recv():
        for r in (responses or []):
            yield r

    mock_instance.receive_responses = _recv

    mock_cls = lambda **kwargs: mock_instance  # noqa: E731
    return mock_cls, mock_instance


# --- Auth tests ---

class TestWebSocketAuth:
    def test_no_token_rejected(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/session"):
                pass

    def test_invalid_token_rejected(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/session?token=wrong"):
                pass

    def test_missing_env_var_rejects_all(self, client, monkeypatch):
        monkeypatch.delenv("WS_AUTH_TOKEN", raising=False)
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}"):
                pass


# --- Connection and greeting ---

class TestWebSocketConnection:
    @patch("api.websocket.GeminiLiveSession")
    def test_connection_sends_greeting(self, mock_cls, client):
        mock_cls_factory, mock_instance = _make_mock_session_class()
        mock_cls.side_effect = lambda **kwargs: mock_cls_factory(**kwargs)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "connection"
            assert msg["status"] == "connected"
            assert "Anchor" in msg["message"]


# --- Audio forwarding ---

class TestAudioForwarding:
    @patch("api.websocket.GeminiLiveSession")
    def test_send_binary_audio_forwarded(self, mock_cls, client):
        mock_cls_factory, mock_instance = _make_mock_session_class()
        mock_cls.side_effect = lambda **kwargs: mock_cls_factory(**kwargs)
        audio = make_pcm16_silence(0.1)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            ws.receive_json()  # consume greeting
            ws.send_bytes(audio)

        mock_instance.send_audio.assert_called_once_with(audio)

    @patch("api.websocket.GeminiLiveSession")
    def test_oversized_audio_rejected(self, mock_cls, client):
        mock_cls_factory, mock_instance = _make_mock_session_class()
        mock_cls.side_effect = lambda **kwargs: mock_cls_factory(**kwargs)
        oversized = b"\x00" * (MAX_AUDIO_CHUNK_SIZE + 1)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            ws.receive_json()  # greeting
            ws.send_bytes(oversized)
            err = ws.receive_json()
            assert err["type"] == "error"
            assert "too large" in err["message"].lower()

        mock_instance.send_audio.assert_not_called()


# --- Text forwarding ---

class TestTextForwarding:
    @patch("api.websocket.GeminiLiveSession")
    def test_send_text_forwarded(self, mock_cls, client):
        mock_cls_factory, mock_instance = _make_mock_session_class()
        mock_cls.side_effect = lambda **kwargs: mock_cls_factory(**kwargs)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            ws.receive_json()  # greeting
            ws.send_json({"type": "text", "content": "I have contamination OCD"})

        mock_instance.send_text.assert_called_once_with("I have contamination OCD")

    @patch("api.websocket.GeminiLiveSession")
    def test_invalid_json_ignored(self, mock_cls, client):
        mock_cls_factory, mock_instance = _make_mock_session_class()
        mock_cls.side_effect = lambda **kwargs: mock_cls_factory(**kwargs)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            ws.receive_json()  # greeting
            ws.send_text("not valid json {{{")

        mock_instance.send_text.assert_not_called()


# --- Response forwarding ---

class TestResponseForwarding:
    @patch("api.websocket.GeminiLiveSession")
    def test_gemini_text_response_forwarded(self, mock_cls, client):
        responses = [{"type": "text", "content": "Tell me more about your fear."}]
        mock_cls_factory, mock_instance = _make_mock_session_class(responses)
        mock_cls.side_effect = lambda **kwargs: mock_cls_factory(**kwargs)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            greeting = ws.receive_json()
            assert greeting["type"] == "connection"
            msg = ws.receive_json()
            assert msg["type"] == "text"
            assert "Tell me more" in msg["content"]

    @patch("api.websocket.GeminiLiveSession")
    def test_gemini_audio_response_forwarded(self, mock_cls, client):
        import base64
        audio_bytes = make_pcm16_silence(0.1, sample_rate=24000)
        b64 = base64.b64encode(audio_bytes).decode()
        responses = [{"type": "audio", "data": b64, "mime_type": "audio/pcm;rate=24000"}]
        mock_cls_factory, mock_instance = _make_mock_session_class(responses)
        mock_cls.side_effect = lambda **kwargs: mock_cls_factory(**kwargs)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            ws.receive_json()  # greeting
            msg = ws.receive_json()
            assert msg["type"] == "audio"
            decoded = base64.b64decode(msg["data"])
            assert len(decoded) % 2 == 0  # valid PCM16
