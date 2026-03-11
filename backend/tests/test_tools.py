"""Unit tests for the ERP tools."""

import json
from unittest.mock import MagicMock, patch

from agent.tools.hierarchy_builder import hierarchy_builder
from agent.tools.erp_timer import erp_timer
from agent.tools.session_tracker import session_tracker, VALID_ACTIONS, REQUIRED_FIELDS
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

    def test_level_too_low(self):
        result = erp_timer(level=0, duration_minutes=10)
        assert "error" in result

    def test_level_too_high(self):
        result = erp_timer(level=11, duration_minutes=10)
        assert "error" in result

    def test_duration_too_short(self):
        result = erp_timer(level=3, duration_minutes=0)
        assert "error" in result

    def test_duration_too_long(self):
        result = erp_timer(level=3, duration_minutes=121)
        assert "error" in result

    def test_boundary_values(self):
        for level in (1, 10):
            for duration in (1, 120):
                result = erp_timer(level=level, duration_minutes=duration)
                assert "timer_id" in result


# --- session_tracker ---

class TestSessionTracker:
    def test_start_session(self):
        result = session_tracker("start_session", {"user_id": "u1"})
        assert result["success"] is True

    def test_log_level(self):
        result = session_tracker("log_level", {
            "session_id": "s1", "level": 5,
            "anxiety_peak": 7, "resistance": True,
        })
        assert result["success"] is True

    def test_end_session(self):
        result = session_tracker("end_session", {"session_id": "s1"})
        assert result["success"] is True

    def test_get_history(self):
        result = session_tracker("get_history", {"user_id": "u1"})
        assert result["success"] is True

    def test_invalid_action(self):
        result = session_tracker("delete_all", {})
        assert result["success"] is False
        assert "error" in result

    def test_missing_required_fields(self):
        result = session_tracker("log_level", {"session_id": "s1"})
        assert result["success"] is False
        assert "Missing required fields" in result["error"]


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
