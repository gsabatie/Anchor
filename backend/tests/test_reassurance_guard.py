"""Unit tests for the reassurance guard tool."""

import pytest

from agent.tools.reassurance_guard import (
    REASSURANCE_PATTERNS,
    _ERP_REDIRECTS,
    _check_patterns,
    reassurance_guard,
)


class TestReassuranceGuardBlocking:
    """Every known reassurance pattern must be blocked."""

    @pytest.mark.parametrize("pattern", REASSURANCE_PATTERNS)
    def test_blocks_each_pattern(self, pattern):
        result = reassurance_guard(pattern)
        assert result["allowed"] is False
        assert result["replacement"] in _ERP_REDIRECTS
        assert result["matched_pattern"] is not None

    @pytest.mark.parametrize("pattern", REASSURANCE_PATTERNS)
    def test_case_insensitive(self, pattern):
        result = reassurance_guard(pattern.upper())
        assert result["allowed"] is False

    @pytest.mark.parametrize("pattern", REASSURANCE_PATTERNS)
    def test_blocks_pattern_in_longer_sentence(self, pattern):
        sentence = f"I think {pattern}, so relax."
        result = reassurance_guard(sentence)
        assert result["allowed"] is False


class TestRegexPatterns:
    """Regex-based patterns for variants."""

    @pytest.mark.parametrize("text", [
        "You're fine.",
        "You are perfectly fine.",
        "You're totally okay.",
        "You are completely safe.",
        "You're alright.",
    ])
    def test_blocks_youre_positive_adjective(self, text):
        result = reassurance_guard(text)
        assert result["allowed"] is False

    @pytest.mark.parametrize("text", [
        "There's no risk at all.",
        "There is no threat here.",
        "There's no problem.",
        "There is no harm.",
    ])
    def test_blocks_theres_no_threat(self, text):
        result = reassurance_guard(text)
        assert result["allowed"] is False

    @pytest.mark.parametrize("text", [
        "Nothing will happen.",
        "Nothing bad could happen.",
        "Nothing wrong is going to happen.",
    ])
    def test_blocks_nothing_will_happen(self, text):
        result = reassurance_guard(text)
        assert result["allowed"] is False

    @pytest.mark.parametrize("text", [
        "I can confirm that it's clean.",
        "I can verify everything is fine.",
        "I can assure you it's safe.",
    ])
    def test_blocks_i_can_confirm(self, text):
        result = reassurance_guard(text)
        assert result["allowed"] is False


class TestReassuranceGuardAllowing:
    """Neutral therapeutic phrases must pass through."""

    @pytest.mark.parametrize("text", [
        "Tell me more about what you're feeling.",
        "Where are you on a scale of 0 to 10?",
        "Let's work through this together.",
        "That takes courage.",
        "I hear you.",
        "Stay with the feeling.",
        "Notice the anxiety without judging it.",
        "What are you feeling in your body right now?",
        "The wave has a peak. You're at the peak.",
        "",
        "   ",
    ])
    def test_allows_neutral_text(self, text):
        result = reassurance_guard(text)
        assert result["allowed"] is True
        assert result["replacement"] is None
        assert result["matched_pattern"] is None


class TestCheckPatterns:
    """Direct tests for the _check_patterns helper."""

    def test_returns_matched_string(self):
        matched = _check_patterns("Don't worry about it")
        assert matched == "don't worry"

    def test_returns_none_for_clean_text(self):
        assert _check_patterns("I hear you.") is None

    def test_regex_match_returns_matched_group(self):
        matched = _check_patterns("You're perfectly fine, relax.")
        assert matched is not None
        assert "fine" in matched.lower()
