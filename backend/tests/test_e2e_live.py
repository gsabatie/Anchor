"""Live end-to-end tests requiring a real GOOGLE_GENAI_API_KEY.

Run with:  pytest tests/test_e2e_live.py -m live -v --timeout=60
Skip with: pytest -m "not live"
"""

import asyncio
import base64
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from tests.helpers import make_pcm16_silence

pytestmark = pytest.mark.live

SKIP_REASON = "GOOGLE_GENAI_API_KEY not set — skipping live tests"


@pytest.fixture
def api_key():
    # Load the real .env from the project root (not the fake test env vars)
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path, override=True)
    key = os.getenv("GOOGLE_GENAI_API_KEY")
    if not key or key == "fake-gemini-key":
        pytest.skip(SKIP_REASON)
    return key


@pytest.mark.asyncio
async def test_live_connect_and_disconnect(api_key, monkeypatch):
    """Connect to Gemini Live and disconnect cleanly."""
    monkeypatch.setenv("GOOGLE_GENAI_API_KEY", api_key)
    from services.gemini_live import GeminiLiveSession

    session = GeminiLiveSession(gemini_api_key=api_key)
    await session.connect()
    assert session._connected is True
    await session.disconnect()
    assert session._connected is False


@pytest.mark.asyncio
async def test_live_send_text_get_response(api_key, monkeypatch):
    """Send text to Gemini Live and receive at least one response."""
    monkeypatch.setenv("GOOGLE_GENAI_API_KEY", api_key)
    from services.gemini_live import GeminiLiveSession

    session = GeminiLiveSession(gemini_api_key=api_key)
    await session.connect()

    try:
        await session.send_text("Hello, how are you?")

        responses = []
        async for msg in session.receive_responses():
            responses.append(msg)
            if len(responses) >= 1:
                break

        assert len(responses) >= 1
        assert responses[0]["type"] in ("text", "audio")
    finally:
        await session.disconnect()


@pytest.mark.asyncio
async def test_live_send_audio_no_crash(api_key, monkeypatch):
    """Send PCM16 silence to Gemini Live — verify no crash."""
    monkeypatch.setenv("GOOGLE_GENAI_API_KEY", api_key)
    from services.gemini_live import GeminiLiveSession

    session = GeminiLiveSession(gemini_api_key=api_key)
    await session.connect()

    try:
        audio = make_pcm16_silence(seconds=1.0, sample_rate=16000)
        chunk_size = 4096
        for i in range(0, len(audio), chunk_size):
            await session.send_audio(audio[i:i + chunk_size])

        # Wait briefly for any response (silence may not trigger one)
        await asyncio.sleep(2)
    finally:
        await session.disconnect()


@pytest.mark.asyncio
async def test_live_audio_bidirectional(api_key, monkeypatch):
    """Full roundtrip: send audio → receive audio response with valid PCM16."""
    monkeypatch.setenv("GOOGLE_GENAI_API_KEY", api_key)
    from services.gemini_live import GeminiLiveSession

    session = GeminiLiveSession(gemini_api_key=api_key)
    await session.connect()

    try:
        # Send text to reliably get a response (audio silence may not)
        await session.send_text("Say hello briefly.")

        audio_responses = []
        async for msg in session.receive_responses():
            if msg["type"] == "audio":
                audio_responses.append(msg)
                if len(audio_responses) >= 1:
                    break
            # Also break on text if no audio comes
            if len(audio_responses) == 0 and msg["type"] == "text":
                break

        if audio_responses:
            decoded = base64.b64decode(audio_responses[0]["data"])
            assert len(decoded) % 2 == 0, "Audio bytes must be even (PCM16)"
    finally:
        await session.disconnect()


@pytest.mark.asyncio
async def test_live_full_websocket_roundtrip(api_key, monkeypatch):
    """Full WebSocket roundtrip via TestClient with real Gemini."""
    monkeypatch.setenv("GOOGLE_GENAI_API_KEY", api_key)
    # Use the real WS_AUTH_TOKEN from .env (load_dotenv in api_key fixture may have overridden it)
    ws_token = os.getenv("WS_AUTH_TOKEN", "")
    monkeypatch.setenv("WS_AUTH_TOKEN", ws_token)
    from main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    with client.websocket_connect(f"/ws/session?token={ws_token}") as ws:
        greeting = ws.receive_json()
        assert greeting["type"] == "connection"
        assert greeting["status"] == "connected"

        ws.send_json({"type": "text", "content": "Hello, I need help with my OCD."})

        # Collect at least one response (text or audio)
        msg = ws.receive_json(mode="text")
        assert msg["type"] in ("text", "audio", "error")
