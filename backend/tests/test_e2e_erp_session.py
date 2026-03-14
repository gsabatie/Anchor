"""End-to-end tests for a complete ERP therapy session.

Tests the full session lifecycle through the WebSocket endpoint and the
tool execution pipeline:
  - Complete session flow: intake → hierarchy → exposure → timer → debrief
  - Tool execution via _process_response: hierarchy_builder, image_generator,
    erp_timer, session_tracker
  - Reassurance guard blocking during active sessions
  - Multi-level exposure progression

External services (Gemini Live, Firestore, Vertex AI) are mocked.

Run with: pytest tests/test_e2e_erp_session.py -v
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.helpers import TEST_TOKEN, make_pcm16_silence


# ─── Mock Gemini response builders ──────────────────────────────────────────


def _text_response(text):
    """Build a mock Gemini Live response containing text."""
    part = SimpleNamespace(text=text, inline_data=None, thought=False)
    model_turn = SimpleNamespace(parts=[part])
    content = SimpleNamespace(model_turn=model_turn)
    return SimpleNamespace(server_content=content, tool_call=None)


def _tool_call_response(name, args):
    """Build a mock Gemini Live response containing a function call."""
    fc = SimpleNamespace(name=name, args=args)
    tool_call = SimpleNamespace(function_calls=[fc])
    return SimpleNamespace(server_content=None, tool_call=tool_call)


# ─── WebSocket mock factory ─────────────────────────────────────────────────


def _full_session_script():
    """Scripted messages simulating a complete ERP session through the WS."""
    return [
        # Intake response
        {"type": "text", "content": "I hear you. Tell me more about your contamination fear."},
        # Hierarchy announcement
        {"type": "text", "content": "I've built your exposure hierarchy. Let's begin with level 1."},
        # Exposure image
        {
            "type": "exposure_image",
            "image_base64": "data:image/png;base64,AAAA",
            "prompt_used": "Realistic photograph: door handle in a public restroom",
            "level": 1,
        },
        # Timer
        {
            "type": "timer",
            "action": "start",
            "level": 1,
            "duration_minutes": 10,
            "timer_id": "tmr-001",
            "started_at": 1700000000.0,
            "duration_seconds": 600,
            "recommended_duration": 600,
            "coaching_schedule": [
                {"offset_seconds": 60, "phase": "opening", "message": "The timer is running."},
                {"offset_seconds": 300, "phase": "peak", "message": "You're at the peak."},
                {"offset_seconds": 600, "phase": "closing", "message": "You rode through it."},
            ],
        },
        # Coaching
        {"type": "text", "content": "Where are you on a scale of 0 to 10?"},
        {"type": "text", "content": "That's brave. The wave has a peak and it will come down."},
        # Descent + close
        {"type": "text", "content": "You rode through it. That's ERP. I'm saving this session."},
        {"type": "text", "content": "You worked hard today. I've saved this session."},
    ]


def _make_ws_mock(script):
    """Build a mock GeminiLiveSession yielding a scripted sequence."""
    instance = AsyncMock()
    instance.connect = AsyncMock()
    instance.disconnect = AsyncMock()
    instance.send_audio = AsyncMock()
    instance.send_text = AsyncMock()

    async def _recv():
        for msg in script:
            yield msg

    instance.receive_responses = _recv
    factory = lambda **kw: instance  # noqa: E731
    return factory, instance


# ═══════════════════════════════════════════════════════════════════════════════
# 1. WebSocket-level e2e: full session lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestERPSessionWebSocket:
    """Complete ERP session through the WebSocket endpoint."""

    @patch("api.websocket.GeminiLiveSession")
    def test_complete_session_flow(self, mock_cls, client):
        """Full lifecycle: greeting → intake → hierarchy → exposure → timer → debrief."""
        script = _full_session_script()
        factory, _ = _make_ws_mock(script)
        mock_cls.side_effect = lambda **kw: factory(**kw)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            greeting = ws.receive_json()
            assert greeting["type"] == "connection"
            assert greeting["status"] == "connected"
            assert "Anchor" in greeting["message"]

            ws.send_json({
                "type": "text",
                "content": "I have contamination OCD. I can't touch door handles.",
            })

            received = [ws.receive_json() for _ in range(len(script))]
            types_seq = [m["type"] for m in received]

            assert types_seq == [
                "text", "text",        # intake reply + hierarchy announcement
                "exposure_image",      # generated image
                "timer",               # ERP timer started
                "text", "text",        # coaching during exposure
                "text", "text",        # descent + session saved
            ]

    @patch("api.websocket.GeminiLiveSession")
    def test_exposure_image_fields(self, mock_cls, client):
        """Exposure image contains level, base64 data, and prompt."""
        factory, _ = _make_ws_mock(_full_session_script())
        mock_cls.side_effect = lambda **kw: factory(**kw)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            ws.receive_json()  # greeting
            ws.send_json({"type": "text", "content": "contamination OCD"})
            msgs = [ws.receive_json() for _ in range(len(_full_session_script()))]

            img = next(m for m in msgs if m["type"] == "exposure_image")
            assert img["level"] == 1
            assert img["image_base64"].startswith("data:image/png;base64,")
            assert len(img["prompt_used"]) > 0

    @patch("api.websocket.GeminiLiveSession")
    def test_timer_has_coaching_schedule(self, mock_cls, client):
        """Timer message contains a coaching schedule with phases."""
        factory, _ = _make_ws_mock(_full_session_script())
        mock_cls.side_effect = lambda **kw: factory(**kw)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            ws.receive_json()
            ws.send_json({"type": "text", "content": "contamination OCD"})
            msgs = [ws.receive_json() for _ in range(len(_full_session_script()))]

            timer = next(m for m in msgs if m["type"] == "timer")
            assert timer["action"] == "start"
            assert timer["level"] == 1
            assert timer["duration_minutes"] == 10

            phases = [s["phase"] for s in timer["coaching_schedule"]]
            assert "opening" in phases
            assert "closing" in phases

    @patch("api.websocket.GeminiLiveSession")
    def test_user_sends_anxiety_rating(self, mock_cls, client):
        """User anxiety rating is forwarded to Gemini via send_text."""
        factory, instance = _make_ws_mock(_full_session_script())
        mock_cls.side_effect = lambda **kw: factory(**kw)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            ws.receive_json()
            ws.send_json({"type": "text", "content": "contamination OCD"})
            for _ in range(len(_full_session_script())):
                ws.receive_json()
            ws.send_json({"type": "text", "content": "I'm at a 7 right now"})

        instance.send_text.assert_any_call("I'm at a 7 right now")

    @patch("api.websocket.GeminiLiveSession")
    def test_audio_during_session(self, mock_cls, client):
        """Raw PCM16 audio is forwarded during the session."""
        factory, instance = _make_ws_mock(_full_session_script())
        mock_cls.side_effect = lambda **kw: factory(**kw)
        audio = make_pcm16_silence(0.5)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            ws.receive_json()
            ws.send_bytes(audio)

        instance.send_audio.assert_called_once_with(audio)

    @patch("api.websocket.GeminiLiveSession")
    def test_multi_level_progression(self, mock_cls, client):
        """Two exposure levels in a single session."""
        script = [
            {"type": "text", "content": "Let's start with level 1."},
            {"type": "exposure_image", "image_base64": "data:image/png;base64,L1",
             "prompt_used": "level 1 scene", "level": 1},
            {"type": "timer", "action": "start", "level": 1, "duration_minutes": 10,
             "timer_id": "t1", "started_at": 1.0, "duration_seconds": 600,
             "recommended_duration": 600, "coaching_schedule": []},
            {"type": "text", "content": "Great work. Moving to level 2."},
            {"type": "exposure_image", "image_base64": "data:image/png;base64,L2",
             "prompt_used": "level 2 scene", "level": 2},
            {"type": "timer", "action": "start", "level": 2, "duration_minutes": 15,
             "timer_id": "t2", "started_at": 2.0, "duration_seconds": 900,
             "recommended_duration": 900, "coaching_schedule": []},
            {"type": "text", "content": "Session complete."},
        ]
        factory, _ = _make_ws_mock(script)
        mock_cls.side_effect = lambda **kw: factory(**kw)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            ws.receive_json()
            ws.send_json({"type": "text", "content": "contamination OCD"})
            msgs = [ws.receive_json() for _ in range(len(script))]

            images = [m for m in msgs if m["type"] == "exposure_image"]
            assert len(images) == 2
            assert images[0]["level"] == 1
            assert images[1]["level"] == 2

            timers = [m for m in msgs if m["type"] == "timer"]
            assert len(timers) == 2
            assert timers[0]["duration_minutes"] == 10
            assert timers[1]["duration_minutes"] == 15

    @patch("api.websocket.GeminiLiveSession")
    def test_session_handles_disconnect_gracefully(self, mock_cls, client):
        """No crash when client disconnects mid-session."""
        factory, instance = _make_ws_mock(_full_session_script())
        mock_cls.side_effect = lambda **kw: factory(**kw)

        with client.websocket_connect(f"/ws/session?token={TEST_TOKEN}") as ws:
            ws.receive_json()
            # disconnect immediately without consuming responses

        instance.disconnect.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Tool execution pipeline via _process_response
# ═══════════════════════════════════════════════════════════════════════════════


class TestERPToolPipeline:
    """Test tool execution through GeminiLiveSession._process_response.

    External services are mocked but the real tool logic runs.
    """

    @pytest.fixture
    def gemini_session(self):
        """GeminiLiveSession with mocked Gemini client."""
        with patch("services.gemini_live.genai"):
            from services.gemini_live import GeminiLiveSession
            session = GeminiLiveSession(gemini_api_key="fake-key")
            session.session = AsyncMock()
            session._connected = True
            return session

    @pytest.mark.asyncio
    async def test_erp_timer_produces_timer_message(self, gemini_session):
        """erp_timer tool returns a timer message with coaching schedule."""
        response = _tool_call_response("erp_timer", {"level": 3, "duration_minutes": 15})
        messages = await gemini_session._process_response(response)

        assert len(messages) == 1
        timer = messages[0]
        assert timer["type"] == "timer"
        assert timer["action"] == "start"
        assert timer["level"] == 3
        assert timer["duration_minutes"] == 15
        assert timer["duration_seconds"] == 900
        assert len(timer["coaching_schedule"]) >= 3

        phases = {s["phase"] for s in timer["coaching_schedule"]}
        assert "closing" in phases

        gemini_session.session.send_tool_response.assert_called_once()

    @pytest.mark.asyncio
    @patch("agent.tools.image_generator._ensure_vertex_init")
    @patch("agent.tools.image_generator.ImageGenerationModel")
    async def test_image_generator_produces_exposure_image(
        self, mock_model_cls, mock_init, gemini_session,
    ):
        """image_generator returns an exposure_image message with base64 data."""
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_image = MagicMock()
        mock_image._image_bytes = fake_png
        mock_model = MagicMock()
        mock_model.generate_images.return_value = MagicMock(images=[mock_image])
        mock_model_cls.from_pretrained.return_value = mock_model

        response = _tool_call_response("image_generator", {
            "situation": "touching a door handle",
            "level": 5,
            "toc_type": "contamination",
        })
        messages = await gemini_session._process_response(response)

        assert len(messages) == 1
        img = messages[0]
        assert img["type"] == "exposure_image"
        assert img["level"] == 5
        assert img["image_base64"].startswith("data:image/png;base64,")
        assert len(img["prompt_used"]) > 0
        assert "contamination" in img["prompt_used"]

    @pytest.mark.asyncio
    @patch("agent.tools.session_tracker._get_db")
    async def test_session_tracker_start_session(self, mock_db, gemini_session):
        """session_tracker start_session creates a Firestore doc."""
        mock_doc_ref = MagicMock()
        mock_db.return_value.collection.return_value.document.return_value = mock_doc_ref

        response = _tool_call_response("session_tracker", {
            "action": "start_session",
            "session_data": {"user_id": "user-42", "toc_type": "contamination"},
        })
        messages = await gemini_session._process_response(response)

        # session_tracker doesn't produce client-side messages
        assert len(messages) == 0

        func_resp = gemini_session.session.send_tool_response.call_args.kwargs[
            "function_responses"
        ][0]
        assert func_resp.name == "session_tracker"
        assert func_resp.response["success"] is True
        assert "session_id" in func_resp.response

        mock_doc_ref.set.assert_called_once()
        doc_data = mock_doc_ref.set.call_args[0][0]
        assert doc_data["user_id"] == "user-42"
        assert doc_data["status"] == "active"

    @pytest.mark.asyncio
    @patch("agent.tools.session_tracker._get_db")
    async def test_session_tracker_log_level(self, mock_db, gemini_session):
        """session_tracker log_level appends an exposure entry."""
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "status": "active",
            "toc_type": "contamination",
        }
        mock_doc_ref.get.return_value = mock_doc
        mock_db.return_value.collection.return_value.document.return_value = mock_doc_ref

        response = _tool_call_response("session_tracker", {
            "action": "log_level",
            "session_data": {
                "session_id": "sess-001",
                "level": 3,
                "anxiety_peak": 7,
                "resistance": True,
                "duration_seconds": 600,
            },
        })
        messages = await gemini_session._process_response(response)

        assert len(messages) == 0

        func_resp = gemini_session.session.send_tool_response.call_args.kwargs[
            "function_responses"
        ][0]
        assert func_resp.response["success"] is True
        entry = func_resp.response["level_entry"]
        assert entry["level"] == 3
        assert entry["anxiety_peak"] == 7
        assert entry["resistance"] is True

        mock_doc_ref.update.assert_called_once()

    @pytest.mark.asyncio
    @patch("agent.tools.session_tracker._get_db")
    async def test_session_tracker_end_session(self, mock_db, gemini_session):
        """session_tracker end_session marks session completed with summary."""
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "status": "active",
            "started_at": 1700000000.0,
            "levels": [
                {"level": 1, "anxiety_peak": 5, "resistance": True},
                {"level": 2, "anxiety_peak": 7, "resistance": True},
            ],
        }
        mock_doc_ref.get.return_value = mock_doc
        mock_db.return_value.collection.return_value.document.return_value = mock_doc_ref

        response = _tool_call_response("session_tracker", {
            "action": "end_session",
            "session_data": {"session_id": "sess-001"},
        })
        messages = await gemini_session._process_response(response)

        assert len(messages) == 0

        result = gemini_session.session.send_tool_response.call_args.kwargs[
            "function_responses"
        ][0].response
        assert result["success"] is True
        assert result["summary"]["total_levels"] == 2
        assert result["summary"]["max_level"] == 2
        assert result["summary"]["max_anxiety_peak"] == 7
        assert result["summary"]["resistance_count"] == 2

        update_data = mock_doc_ref.update.call_args[0][0]
        assert update_data["status"] == "completed"

    @pytest.mark.asyncio
    @patch("agent.tools.hierarchy_builder.get_firestore_client")
    @patch("agent.tools.hierarchy_builder.genai")
    async def test_hierarchy_builder_produces_10_levels(
        self, mock_genai, mock_firestore, gemini_session,
    ):
        """hierarchy_builder generates 10 sorted levels and saves to Firestore."""
        levels = [
            {"level": i, "situation": f"Situation niveau {i}", "anxiety_estimate": i}
            for i in range(1, 11)
        ]
        mock_response = MagicMock()
        mock_response.text = json.dumps(levels)
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response

        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "hierarchy-001"
        mock_firestore.return_value.collection.return_value.document.return_value = mock_doc_ref

        response = _tool_call_response("hierarchy_builder", {
            "toc_description": "I'm afraid of touching dirty surfaces",
            "toc_type": "contamination",
        })
        messages = await gemini_session._process_response(response)

        assert len(messages) == 0

        result = gemini_session.session.send_tool_response.call_args.kwargs[
            "function_responses"
        ][0].response
        assert len(result["levels"]) == 10
        assert result["levels"][0]["level"] == 1
        assert result["levels"][9]["level"] == 10
        assert result["hierarchy_id"] == "hierarchy-001"

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, gemini_session):
        """Unknown tool name returns an error without crashing."""
        response = _tool_call_response("nonexistent_tool", {"arg": "val"})
        messages = await gemini_session._process_response(response)

        assert len(messages) == 0
        func_resp = gemini_session.session.send_tool_response.call_args.kwargs[
            "function_responses"
        ][0]
        assert "error" in func_resp.response


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Reassurance guard integration during session
# ═══════════════════════════════════════════════════════════════════════════════


class TestReassuranceGuardInSession:
    """Verify reassurance patterns are blocked inside _process_response."""

    @pytest.fixture
    def gemini_session(self):
        with patch("services.gemini_live.genai"):
            from services.gemini_live import GeminiLiveSession
            session = GeminiLiveSession(gemini_api_key="fake-key")
            session.session = AsyncMock()
            session._connected = True
            return session

    @pytest.mark.asyncio
    async def test_reassurance_blocked_in_text(self, gemini_session):
        """Text containing reassurance is replaced with an ERP redirect."""
        response = _text_response("Don't worry, it's going to be okay.")
        messages = await gemini_session._process_response(response)

        assert len(messages) == 1
        text = messages[0]["content"]
        assert "it's going to be okay" not in text.lower()
        assert "don't worry" not in text.lower()
        assert any(
            phrase in text
            for phrase in ["OCD", "reassure", "cycle", "discomfort", "uncertainty", "compulsion"]
        )

    @pytest.mark.asyncio
    async def test_neutral_text_passes_through(self, gemini_session):
        """Non-reassuring text is passed through unchanged."""
        original = "Where are you on a scale of 0 to 10 right now?"
        response = _text_response(original)
        messages = await gemini_session._process_response(response)

        assert len(messages) == 1
        assert messages[0]["content"] == original

    @pytest.mark.asyncio
    async def test_safety_confirmation_blocked(self, gemini_session):
        """Safety-confirming statements are blocked."""
        response = _text_response("The door is locked, you are safe.")
        messages = await gemini_session._process_response(response)

        assert len(messages) == 1
        assert "you are safe" not in messages[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_erp_coaching_passes_through(self, gemini_session):
        """Legitimate ERP coaching language is not blocked."""
        coaching = "I hear you. Stay with the discomfort. The wave will pass on its own."
        response = _text_response(coaching)
        messages = await gemini_session._process_response(response)

        assert len(messages) == 1
        assert messages[0]["content"] == coaching

    @pytest.mark.asyncio
    async def test_thought_parts_skipped(self, gemini_session):
        """Internal thinking/reasoning parts are not forwarded."""
        thought_part = SimpleNamespace(
            text="Let me think about what to say next...",
            inline_data=None,
            thought=True,
        )
        real_part = SimpleNamespace(
            text="Where are you on 0 to 10?",
            inline_data=None,
            thought=False,
        )
        model_turn = SimpleNamespace(parts=[thought_part, real_part])
        content = SimpleNamespace(model_turn=model_turn)
        response = SimpleNamespace(server_content=content, tool_call=None)

        messages = await gemini_session._process_response(response)

        assert len(messages) == 1
        assert messages[0]["content"] == "Where are you on 0 to 10?"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Full pipeline: multi-step ERP session via _process_response
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullERPPipeline:
    """Simulate a multi-step ERP session by feeding sequential responses
    through _process_response, exercising real tool logic end-to-end."""

    @pytest.fixture
    def gemini_session(self):
        with patch("services.gemini_live.genai"):
            from services.gemini_live import GeminiLiveSession
            session = GeminiLiveSession(gemini_api_key="fake-key")
            session.session = AsyncMock()
            session._connected = True
            return session

    @pytest.mark.asyncio
    @patch("agent.tools.image_generator._ensure_vertex_init")
    @patch("agent.tools.image_generator.ImageGenerationModel")
    @patch("agent.tools.session_tracker._get_db")
    @patch("agent.tools.hierarchy_builder.get_firestore_client")
    @patch("agent.tools.hierarchy_builder.genai")
    async def test_complete_session_through_tools(
        self,
        mock_hierarchy_genai,
        mock_hierarchy_firestore,
        mock_session_db,
        mock_imagen_cls,
        mock_vertex_init,
        gemini_session,
    ):
        """Walk through a full ERP session: start → hierarchy → image → timer
        → log_level → end, verifying each tool's output and side effects."""

        # ── Mock setup ──────────────────────────────────────────────────

        # Hierarchy: Gemini returns 10 levels
        hierarchy_levels = [
            {"level": i, "situation": f"Situation {i}", "anxiety_estimate": i}
            for i in range(1, 11)
        ]
        mock_hierarchy_response = MagicMock()
        mock_hierarchy_response.text = json.dumps(hierarchy_levels)
        mock_hierarchy_genai.Client.return_value.models.generate_content.return_value = (
            mock_hierarchy_response
        )
        mock_h_doc_ref = MagicMock()
        mock_h_doc_ref.id = "hier-001"
        mock_hierarchy_firestore.return_value.collection.return_value.document.return_value = (
            mock_h_doc_ref
        )

        # Image generator: returns fake PNG
        fake_png = b"\x89PNG" + b"\x00" * 100
        mock_image = MagicMock()
        mock_image._image_bytes = fake_png
        mock_model = MagicMock()
        mock_model.generate_images.return_value = MagicMock(images=[mock_image])
        mock_imagen_cls.from_pretrained.return_value = mock_model

        # Session tracker: mock Firestore for start/log/end
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc_ref.get.return_value = mock_doc
        mock_session_db.return_value.collection.return_value.document.return_value = mock_doc_ref

        all_messages = []

        # ── Step 1: Start session ────────────────────────────────────────
        r = _tool_call_response("session_tracker", {
            "action": "start_session",
            "session_data": {"user_id": "patient-1", "toc_type": "contamination"},
        })
        msgs = await gemini_session._process_response(r)
        all_messages.extend(msgs)

        start_result = gemini_session.session.send_tool_response.call_args.kwargs[
            "function_responses"
        ][0].response
        assert start_result["success"] is True
        session_id = start_result["session_id"]

        # ── Step 2: Build hierarchy ──────────────────────────────────────
        r = _tool_call_response("hierarchy_builder", {
            "toc_description": "Fear of touching contaminated surfaces",
            "toc_type": "contamination",
        })
        msgs = await gemini_session._process_response(r)
        all_messages.extend(msgs)

        hier_result = gemini_session.session.send_tool_response.call_args.kwargs[
            "function_responses"
        ][0].response
        assert len(hier_result["levels"]) == 10

        # ── Step 3: Generate exposure image for level 1 ──────────────────
        r = _tool_call_response("image_generator", {
            "situation": hier_result["levels"][0]["situation"],
            "level": 1,
            "toc_type": "contamination",
        })
        msgs = await gemini_session._process_response(r)
        all_messages.extend(msgs)

        assert len(msgs) == 1
        assert msgs[0]["type"] == "exposure_image"
        assert msgs[0]["level"] == 1

        # ── Step 4: Start ERP timer ──────────────────────────────────────
        r = _tool_call_response("erp_timer", {"level": 1, "duration_minutes": 10})
        msgs = await gemini_session._process_response(r)
        all_messages.extend(msgs)

        assert len(msgs) == 1
        assert msgs[0]["type"] == "timer"
        assert msgs[0]["level"] == 1
        assert len(msgs[0]["coaching_schedule"]) >= 3

        # ── Step 5: Log level result ─────────────────────────────────────
        mock_doc.to_dict.return_value = {
            "status": "active",
            "toc_type": "contamination",
        }

        r = _tool_call_response("session_tracker", {
            "action": "log_level",
            "session_data": {
                "session_id": session_id,
                "level": 1,
                "anxiety_peak": 6,
                "resistance": True,
                "duration_seconds": 600,
            },
        })
        msgs = await gemini_session._process_response(r)
        all_messages.extend(msgs)

        log_result = gemini_session.session.send_tool_response.call_args.kwargs[
            "function_responses"
        ][0].response
        assert log_result["success"] is True
        assert log_result["level_entry"]["anxiety_peak"] == 6

        # ── Step 6: End session ──────────────────────────────────────────
        mock_doc.to_dict.return_value = {
            "status": "active",
            "started_at": 1700000000.0,
            "levels": [
                {"level": 1, "anxiety_peak": 6, "resistance": True},
            ],
        }

        r = _tool_call_response("session_tracker", {
            "action": "end_session",
            "session_data": {"session_id": session_id},
        })
        msgs = await gemini_session._process_response(r)
        all_messages.extend(msgs)

        end_result = gemini_session.session.send_tool_response.call_args.kwargs[
            "function_responses"
        ][0].response
        assert end_result["success"] is True
        assert end_result["summary"]["total_levels"] == 1
        assert end_result["summary"]["max_anxiety_peak"] == 6
        assert end_result["summary"]["resistance_count"] == 1

        # ── Verify overall message flow ──────────────────────────────────
        client_types = [m["type"] for m in all_messages]
        assert "exposure_image" in client_types
        assert "timer" in client_types
        assert client_types.count("exposure_image") == 1
        assert client_types.count("timer") == 1
