"""Unit tests for the ERP tools."""

import json
from unittest.mock import MagicMock, patch

from agent.tools.hierarchy_builder import hierarchy_builder
from agent.tools.erp_timer import erp_timer, _build_coaching_schedule, _recommended_duration
from agent.tools.session_tracker import session_tracker, VALID_ACTIONS, REQUIRED_FIELDS, _COLLECTION
from agent.tools.image_generator import image_generator, _sanitize_prompt, _build_prompt, _get_intensity


# --- helpers ---

def _fake_levels():
    return [
        {"level": i, "situation": f"Situation {i}", "anxiety_estimate": i}
        for i in range(1, 11)
    ]


def _mock_gemini_response(levels):
    response = MagicMock()
    response.text = json.dumps(levels)
    return response


# --- hierarchy_builder ---

class TestHierarchyBuilder:
    @patch("agent.tools.hierarchy_builder.get_firestore_client")
    @patch("agent.tools.hierarchy_builder.genai.Client")
    def test_returns_10_levels(self, mock_client_cls, mock_fs):
        mock_client_cls.return_value.models.generate_content.return_value = _mock_gemini_response(_fake_levels())
        mock_fs.return_value.collection.return_value.document.return_value = MagicMock(id="doc123")

        result = hierarchy_builder("Fear of germs on doorknobs", "contamination")
        assert "levels" in result
        assert len(result["levels"]) == 10
        for level in result["levels"]:
            assert "level" in level
            assert "situation" in level
            assert "anxiety_estimate" in level

    @patch("agent.tools.hierarchy_builder.get_firestore_client")
    @patch("agent.tools.hierarchy_builder.genai.Client")
    def test_levels_are_ordered(self, mock_client_cls, mock_fs):
        mock_client_cls.return_value.models.generate_content.return_value = _mock_gemini_response(_fake_levels())
        mock_fs.return_value.collection.return_value.document.return_value = MagicMock(id="doc123")

        result = hierarchy_builder("Checking the stove", "checking")
        levels = [l["level"] for l in result["levels"]]
        assert levels == list(range(1, 11))

    def test_description_too_long(self):
        result = hierarchy_builder("x" * 2001, "contamination")
        assert "error" in result

    def test_empty_toc_type(self):
        result = hierarchy_builder("Fear of germs", "  ")
        assert "error" in result

    @patch("agent.tools.hierarchy_builder.get_firestore_client")
    @patch("agent.tools.hierarchy_builder.genai.Client")
    def test_prompt_contains_toc_info(self, mock_client_cls, mock_fs):
        mock_gen = mock_client_cls.return_value.models.generate_content
        mock_gen.return_value = _mock_gemini_response(_fake_levels())
        mock_fs.return_value.collection.return_value.document.return_value = MagicMock(id="doc1")

        hierarchy_builder("Peur des germes", "contamination")

        prompt = mock_gen.call_args[1].get("contents") or mock_gen.call_args[0][1]
        assert "contamination" in prompt
        assert "Peur des germes" in prompt

    @patch("agent.tools.hierarchy_builder.get_firestore_client")
    @patch("agent.tools.hierarchy_builder.genai.Client")
    def test_firestore_persistence(self, mock_client_cls, mock_fs):
        mock_client_cls.return_value.models.generate_content.return_value = _mock_gemini_response(_fake_levels())
        mock_doc = MagicMock(id="abc123")
        mock_fs.return_value.collection.return_value.document.return_value = mock_doc

        result = hierarchy_builder("Fear of germs", "contamination")

        mock_doc.set.assert_called_once()
        saved = mock_doc.set.call_args[0][0]
        assert saved["toc_type"] == "contamination"
        assert len(saved["levels"]) == 10
        assert result["hierarchy_id"] == "abc123"

    @patch("agent.tools.hierarchy_builder.get_firestore_client")
    @patch("agent.tools.hierarchy_builder.genai.Client")
    def test_firestore_failure_is_non_fatal(self, mock_client_cls, mock_fs):
        mock_client_cls.return_value.models.generate_content.return_value = _mock_gemini_response(_fake_levels())
        mock_fs.side_effect = Exception("Firestore down")

        result = hierarchy_builder("Fear of germs", "contamination")
        assert "levels" in result
        assert "hierarchy_id" not in result

    @patch("agent.tools.hierarchy_builder.genai.Client")
    def test_gemini_failure_returns_error(self, mock_client_cls):
        mock_client_cls.return_value.models.generate_content.side_effect = Exception("Gemini unavailable")

        result = hierarchy_builder("Fear of germs", "contamination")
        assert "error" in result

    @patch("agent.tools.hierarchy_builder.get_firestore_client")
    @patch("agent.tools.hierarchy_builder.genai.Client")
    def test_wrong_level_count_returns_error(self, mock_client_cls, mock_fs):
        bad_levels = [{"level": 1, "situation": "Only one", "anxiety_estimate": 1}]
        mock_client_cls.return_value.models.generate_content.return_value = _mock_gemini_response(bad_levels)

        result = hierarchy_builder("Fear of germs", "contamination")
        assert "error" in result


# --- erp_timer ---

class TestErpTimer:
    def test_valid_timer(self):
        result = erp_timer(level=5, duration_minutes=15)
        assert "timer_id" in result
        assert "started_at" in result
        assert result["duration_seconds"] == 15 * 60
        assert result["level"] == 5
        assert "coaching_schedule" in result
        assert len(result["coaching_schedule"]) > 0

    def test_level_too_low(self):
        assert "error" in erp_timer(level=0, duration_minutes=10)

    def test_level_too_high(self):
        assert "error" in erp_timer(level=11, duration_minutes=10)

    def test_duration_too_short(self):
        assert "error" in erp_timer(level=3, duration_minutes=0)

    def test_duration_too_long(self):
        assert "error" in erp_timer(level=3, duration_minutes=121)

    def test_boundary_values(self):
        for level in (1, 10):
            for duration in (1, 120):
                result = erp_timer(level=level, duration_minutes=duration)
                assert "timer_id" in result
                assert "coaching_schedule" in result

    def test_schedule_ends_with_closing(self):
        result = erp_timer(level=5, duration_minutes=20)
        last = result["coaching_schedule"][-1]
        assert last["phase"] == "closing"
        assert last["offset_seconds"] == 20 * 60

    def test_schedule_offsets_are_sorted(self):
        result = erp_timer(level=3, duration_minutes=15)
        offsets = [m["offset_seconds"] for m in result["coaching_schedule"]]
        assert offsets == sorted(offsets)

    def test_schedule_phases_follow_order(self):
        result = erp_timer(level=5, duration_minutes=30)
        phases = [m["phase"] for m in result["coaching_schedule"]]
        phase_order = ["opening", "rising", "peak", "falling", "closing"]
        # Each phase should not appear after a later phase
        last_idx = -1
        for phase in phases:
            idx = phase_order.index(phase)
            assert idx >= last_idx
            last_idx = idx

    def test_higher_levels_fewer_checkpoints(self):
        low = _build_coaching_schedule(2, 20)
        high = _build_coaching_schedule(9, 20)
        assert len(low) >= len(high)

    def test_recommended_duration(self):
        assert _recommended_duration(1) == 10
        assert _recommended_duration(5) == 20
        assert _recommended_duration(10) == 40


# --- session_tracker ---

class TestSessionTracker:
    def _mock_db(self):
        """Return a mock Firestore client with a fluent collection API."""
        db = MagicMock()
        self._mock_doc_ref = MagicMock()
        db.collection.return_value.document.return_value = self._mock_doc_ref
        return db

    @patch("agent.tools.session_tracker._get_db")
    def test_start_session(self, mock_get_db):
        mock_get_db.return_value = self._mock_db()

        result = session_tracker("start_session", {"user_id": "u1"})
        assert result["success"] is True
        assert "session_id" in result
        assert "started_at" in result
        self._mock_doc_ref.set.assert_called_once()
        saved = self._mock_doc_ref.set.call_args[0][0]
        assert saved["user_id"] == "u1"
        assert saved["status"] == "active"
        assert saved["levels"] == []

    @patch("agent.tools.session_tracker._get_db")
    def test_start_session_with_toc_info(self, mock_get_db):
        mock_get_db.return_value = self._mock_db()

        result = session_tracker("start_session", {
            "user_id": "u1",
            "toc_type": "contamination",
            "toc_description": "Fear of germs",
        })
        assert result["success"] is True
        saved = self._mock_doc_ref.set.call_args[0][0]
        assert saved["toc_type"] == "contamination"
        assert saved["toc_description"] == "Fear of germs"

    @patch("agent.tools.session_tracker._get_db")
    def test_log_level(self, mock_get_db):
        db = self._mock_db()
        mock_get_db.return_value = db
        # Simulate an existing active session
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"status": "active", "toc_type": "checking"}
        self._mock_doc_ref.get.return_value = mock_doc

        result = session_tracker("log_level", {
            "session_id": "s1", "level": 5,
            "anxiety_peak": 7, "resistance": True,
        })
        assert result["success"] is True
        assert result["level_entry"]["level"] == 5
        assert result["level_entry"]["anxiety_peak"] == 7
        assert result["level_entry"]["resistance"] is True
        self._mock_doc_ref.update.assert_called_once()

    @patch("agent.tools.session_tracker._get_db")
    def test_log_level_session_not_found(self, mock_get_db):
        db = self._mock_db()
        mock_get_db.return_value = db
        mock_doc = MagicMock()
        mock_doc.exists = False
        self._mock_doc_ref.get.return_value = mock_doc

        result = session_tracker("log_level", {
            "session_id": "missing", "level": 3,
            "anxiety_peak": 5, "resistance": False,
        })
        assert result["success"] is False
        assert "not found" in result["error"]

    @patch("agent.tools.session_tracker._get_db")
    def test_log_level_session_not_active(self, mock_get_db):
        db = self._mock_db()
        mock_get_db.return_value = db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"status": "completed"}
        self._mock_doc_ref.get.return_value = mock_doc

        result = session_tracker("log_level", {
            "session_id": "s1", "level": 3,
            "anxiety_peak": 5, "resistance": False,
        })
        assert result["success"] is False
        assert "not active" in result["error"]

    @patch("agent.tools.session_tracker._get_db")
    def test_end_session(self, mock_get_db):
        db = self._mock_db()
        mock_get_db.return_value = db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "status": "active",
            "started_at": 1000.0,
            "levels": [
                {"level": 3, "anxiety_peak": 5, "resistance": True},
                {"level": 5, "anxiety_peak": 8, "resistance": False},
            ],
        }
        self._mock_doc_ref.get.return_value = mock_doc

        result = session_tracker("end_session", {"session_id": "s1"})
        assert result["success"] is True
        assert "summary" in result
        assert result["summary"]["total_levels"] == 2
        assert result["summary"]["max_level"] == 5
        assert result["summary"]["max_anxiety_peak"] == 8
        assert result["summary"]["resistance_count"] == 1
        self._mock_doc_ref.update.assert_called_once()
        update_data = self._mock_doc_ref.update.call_args[0][0]
        assert update_data["status"] == "completed"

    @patch("agent.tools.session_tracker._get_db")
    def test_end_session_already_ended(self, mock_get_db):
        db = self._mock_db()
        mock_get_db.return_value = db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"status": "completed"}
        self._mock_doc_ref.get.return_value = mock_doc

        result = session_tracker("end_session", {"session_id": "s1"})
        assert result["success"] is False
        assert "already ended" in result["error"]

    @patch("agent.tools.session_tracker._get_db")
    def test_get_history(self, mock_get_db):
        db = self._mock_db()
        mock_get_db.return_value = db
        mock_query = MagicMock()
        db.collection.return_value.where.return_value.order_by.return_value.limit.return_value = mock_query

        doc1 = MagicMock()
        doc1.to_dict.return_value = {
            "session_id": "s1", "started_at": 2000.0,
            "ended_at": 3000.0, "status": "completed",
            "toc_type": "contamination",
            "levels": [{"level": 3}],
            "summary": {"total_levels": 1},
        }
        mock_query.stream.return_value = [doc1]

        result = session_tracker("get_history", {"user_id": "u1"})
        assert result["success"] is True
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["session_id"] == "s1"
        assert result["sessions"][0]["total_levels"] == 1

    @patch("agent.tools.session_tracker._get_db")
    def test_get_history_empty(self, mock_get_db):
        db = self._mock_db()
        mock_get_db.return_value = db
        mock_query = MagicMock()
        db.collection.return_value.where.return_value.order_by.return_value.limit.return_value = mock_query
        mock_query.stream.return_value = []

        result = session_tracker("get_history", {"user_id": "u1"})
        assert result["success"] is True
        assert result["sessions"] == []

    def test_invalid_action(self):
        result = session_tracker("delete_all", {})
        assert result["success"] is False
        assert "error" in result

    def test_missing_required_fields(self):
        result = session_tracker("log_level", {"session_id": "s1"})
        assert result["success"] is False
        assert "Missing required fields" in result["error"]

    @patch("agent.tools.session_tracker._get_db")
    def test_firestore_failure(self, mock_get_db):
        mock_get_db.side_effect = Exception("Connection refused")
        result = session_tracker("start_session", {"user_id": "u1"})
        assert result["success"] is False
        assert "failed" in result["error"]


# --- image_generator ---

class TestImageGenerator:
    @patch("agent.tools.image_generator.ImageGenerationModel")
    @patch("agent.tools.image_generator._ensure_vertex_init")
    def test_valid_call(self, mock_init, mock_model_cls):
        fake_image = MagicMock()
        fake_image._image_bytes = b"\x89PNG\r\n\x1a\nfake"
        mock_model = MagicMock()
        mock_model.generate_images.return_value = MagicMock(images=[fake_image])
        mock_model_cls.from_pretrained.return_value = mock_model

        result = image_generator("Dirty doorknob close-up", level=6, toc_type="contamination")
        assert "image_base64" in result
        assert result["image_base64"].startswith("data:image/png;base64,")
        assert "prompt_used" in result
        assert result["level"] == 6
        mock_model.generate_images.assert_called_once()

    @patch("agent.tools.image_generator.ImageGenerationModel")
    @patch("agent.tools.image_generator._ensure_vertex_init")
    def test_no_images_returned(self, mock_init, mock_model_cls):
        mock_model = MagicMock()
        mock_model.generate_images.return_value = MagicMock(images=[])
        mock_model_cls.from_pretrained.return_value = mock_model

        result = image_generator("scene", level=5, toc_type="contamination")
        assert "error" in result
        assert "no results" in result["error"]

    def test_level_out_of_range(self):
        assert "error" in image_generator("scene", level=0, toc_type="checking")
        assert "error" in image_generator("scene", level=11, toc_type="checking")

    def test_empty_situation(self):
        assert "error" in image_generator("", level=5, toc_type="checking")
        assert "error" in image_generator("   ", level=5, toc_type="checking")

    def test_empty_toc_type(self):
        assert "error" in image_generator("scene", level=5, toc_type="")
        assert "error" in image_generator("scene", level=5, toc_type="  ")

    def test_prompt_sanitization(self):
        dirty = "Hello\x00World\x1fTest"
        assert _sanitize_prompt(dirty) == "HelloWorldTest"

    def test_prompt_truncation(self):
        long = "a" * 600
        assert len(_sanitize_prompt(long)) == 500

    def test_intensity_bands(self):
        assert "wide-angle" in _get_intensity(1)
        assert "wide-angle" in _get_intensity(3)
        assert "medium shot" in _get_intensity(4)
        assert "medium shot" in _get_intensity(6)
        assert "close-up" in _get_intensity(7)
        assert "extreme close-up" in _get_intensity(10)

    def test_build_prompt_contains_situation(self):
        prompt = _build_prompt("a dirty doorknob", 5, "contamination")
        assert "dirty doorknob" in prompt
        assert "contamination" in prompt
