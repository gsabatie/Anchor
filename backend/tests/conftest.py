"""Shared fixtures for Anchor backend tests."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from tests.helpers import TEST_TOKEN, FAKE_API_KEY, make_pcm16_silence  # noqa: F401


@pytest.fixture(autouse=True)
def _patch_env(monkeypatch):
    """Set required env vars for every test."""
    monkeypatch.setenv("WS_AUTH_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("GOOGLE_GENAI_API_KEY", FAKE_API_KEY)


@pytest.fixture
def client():
    """FastAPI TestClient with env vars already patched."""
    from main import app
    return TestClient(app)


@pytest.fixture
def sample_pcm16():
    """Factory fixture that returns PCM16 silence bytes."""
    return make_pcm16_silence


@pytest.fixture
def mock_gemini_session():
    """Create a mock GeminiLiveSession that doesn't hit the network."""
    session = AsyncMock()
    session.connect = AsyncMock()
    session.disconnect = AsyncMock()
    session.send_audio = AsyncMock()
    session.send_text = AsyncMock()
    session._connected = True

    async def _empty_responses():
        return
        yield  # make it an async generator

    session.receive_responses = _empty_responses
    return session
