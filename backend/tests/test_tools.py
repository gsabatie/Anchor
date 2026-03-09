"""Unit tests for the ERP tools (stubbed implementations)."""

from agent.tools.hierarchy_builder import hierarchy_builder
from agent.tools.erp_timer import erp_timer
from agent.tools.session_tracker import session_tracker, VALID_ACTIONS, REQUIRED_FIELDS
from agent.tools.image_generator import image_generator, _sanitize_prompt


# --- hierarchy_builder ---

class TestHierarchyBuilder:
    def test_returns_10_levels(self):
        result = hierarchy_builder("Fear of germs on doorknobs", "contamination")
        assert "levels" in result
        assert len(result["levels"]) == 10
        for level in result["levels"]:
            assert "level" in level
            assert "situation" in level
            assert "anxiety_estimate" in level

    def test_levels_are_ordered(self):
        result = hierarchy_builder("Checking the stove", "checking")
        levels = [l["level"] for l in result["levels"]]
        assert levels == list(range(1, 11))

    def test_description_too_long(self):
        result = hierarchy_builder("x" * 2001, "contamination")
        assert "error" in result

    def test_empty_toc_type(self):
        result = hierarchy_builder("Fear of germs", "  ")
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
    def test_valid_call(self):
        result = image_generator("Dirty doorknob close-up", level=6, toc_type="contamination")
        assert "image_url" in result
        assert "prompt_used" in result
        assert "[level 6]" in result["prompt_used"]

    def test_level_out_of_range(self):
        assert "error" in image_generator("scene", level=0, toc_type="checking")
        assert "error" in image_generator("scene", level=11, toc_type="checking")

    def test_prompt_sanitization(self):
        dirty = "Hello\x00World\x1fTest"
        assert _sanitize_prompt(dirty) == "HelloWorldTest"

    def test_prompt_truncation(self):
        long = "a" * 600
        assert len(_sanitize_prompt(long)) == 500
