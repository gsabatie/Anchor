"""Tests for GeminiLiveSession._process_response."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.tools.reassurance_guard import _ERP_REDIRECTS


def _make_session():
    """Create a GeminiLiveSession with mocked client for unit testing."""
    with patch("google.genai.Client"):
        from services.gemini_live import GeminiLiveSession
        session = GeminiLiveSession(gemini_api_key="fake-key")
        session.session = AsyncMock()  # mock the live session object
        return session


def _text_response(text, thought=False):
    """Build a mock Gemini response containing a text part."""
    part = MagicMock()
    part.text = text
    part.inline_data = None
    part.thought = thought

    response = MagicMock()
    response.server_content = MagicMock()
    response.server_content.model_turn = MagicMock()
    response.server_content.model_turn.parts = [part]
    response.tool_call = None
    return response


def _audio_response(audio_bytes, mime_type="audio/pcm;rate=24000"):
    """Build a mock Gemini response containing an audio part."""
    part = MagicMock()
    part.text = None
    part.thought = False
    part.inline_data = MagicMock()
    part.inline_data.data = audio_bytes
    part.inline_data.mime_type = mime_type

    response = MagicMock()
    response.server_content = MagicMock()
    response.server_content.model_turn = MagicMock()
    response.server_content.model_turn.parts = [part]
    response.tool_call = None
    return response


def _tool_call_response(name, args):
    """Build a mock Gemini response containing a tool call."""
    fc = MagicMock()
    fc.name = name
    fc.args = args

    response = MagicMock()
    response.server_content = None
    response.tool_call = MagicMock()
    response.tool_call.function_calls = [fc]
    return response


class TestProcessTextResponse:
    @pytest.mark.asyncio
    async def test_plain_text(self):
        session = _make_session()
        response = _text_response("Tell me more about your fear.")
        messages = await session._process_response(response)
        assert len(messages) == 1
        assert messages[0]["type"] == "text"
        assert messages[0]["content"] == "Tell me more about your fear."

    @pytest.mark.asyncio
    async def test_reassurance_blocked(self):
        session = _make_session()
        response = _text_response("It's going to be okay, don't worry.")
        messages = await session._process_response(response)
        assert len(messages) == 1
        assert messages[0]["type"] == "text"
        assert messages[0]["content"] in _ERP_REDIRECTS

    @pytest.mark.asyncio
    async def test_thought_parts_skipped(self):
        session = _make_session()
        response = _text_response("Internal reasoning...", thought=True)
        messages = await session._process_response(response)
        assert len(messages) == 0


class TestProcessAudioResponse:
    @pytest.mark.asyncio
    async def test_audio_base64_encoded(self):
        session = _make_session()
        raw = b"\x00\x01" * 100  # 200 bytes of PCM
        response = _audio_response(raw)
        messages = await session._process_response(response)
        assert len(messages) == 1
        assert messages[0]["type"] == "audio"
        decoded = base64.b64decode(messages[0]["data"])
        assert decoded == raw
        assert messages[0]["mime_type"] == "audio/pcm;rate=24000"

    @pytest.mark.asyncio
    async def test_audio_even_byte_count(self):
        session = _make_session()
        raw = b"\x00\x00" * 50
        response = _audio_response(raw)
        messages = await session._process_response(response)
        decoded = base64.b64decode(messages[0]["data"])
        assert len(decoded) % 2 == 0


class TestProcessToolCalls:
    @pytest.mark.asyncio
    async def test_image_generator_tool(self):
        session = _make_session()
        response = _tool_call_response("image_generator", {
            "situation": "Dirty doorknob",
            "level": 6,
            "toc_type": "contamination",
        })
        messages = await session._process_response(response)
        # image_generator returns empty url in stub, so no exposure_image message
        # but tool response should have been sent back to Gemini
        session.session.send_tool_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_erp_timer_tool(self):
        session = _make_session()
        response = _tool_call_response("erp_timer", {
            "level": 5,
            "duration_minutes": 15,
        })
        messages = await session._process_response(response)
        # Timer tool returns timer_id, so there should be a timer message
        timer_msgs = [m for m in messages if m["type"] == "timer"]
        assert len(timer_msgs) == 1
        assert timer_msgs[0]["action"] == "start"
        assert timer_msgs[0]["level"] == 5

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        session = _make_session()
        response = _tool_call_response("nonexistent_tool", {})
        messages = await session._process_response(response)
        # Should still send tool response (with error) back to Gemini
        session.session.send_tool_response.assert_called_once()


class TestProcessNoContent:
    @pytest.mark.asyncio
    async def test_empty_response(self):
        session = _make_session()
        response = MagicMock()
        response.server_content = None
        response.tool_call = None
        messages = await session._process_response(response)
        assert messages == []
