"""Unit tests for the reassurance guard tool."""

import pytest

from agent.tools.reassurance_guard import (
    ERP_REDIRECT,
    REASSURANCE_PATTERNS,
    reassurance_guard,
)


class TestReassuranceGuardBlocking:
    """Every known reassurance pattern must be blocked."""

    @pytest.mark.parametrize("pattern", REASSURANCE_PATTERNS)
    def test_blocks_each_pattern(self, pattern):
        result = reassurance_guard(pattern)
        assert result["allowed"] is False
        assert result["replacement"] == ERP_REDIRECT

    @pytest.mark.parametrize("pattern", REASSURANCE_PATTERNS)
    def test_case_insensitive(self, pattern):
        result = reassurance_guard(pattern.upper())
        assert result["allowed"] is False

    @pytest.mark.parametrize("pattern", REASSURANCE_PATTERNS)
    def test_blocks_pattern_in_longer_sentence(self, pattern):
        sentence = f"I think {pattern}, so relax."
        result = reassurance_guard(sentence)
        assert result["allowed"] is False


class TestReassuranceGuardAllowing:
    """Neutral therapeutic phrases must pass through."""

    @pytest.mark.parametrize("text", [
        "Tell me more about what you're feeling.",
        "Where are you on a scale of 1 to 10?",
        "Let's work through this together.",
        "That takes courage.",
        "I hear you.",
        "",
    ])
    def test_allows_neutral_text(self, text):
        result = reassurance_guard(text)
        assert result["allowed"] is True
        assert result["replacement"] is None
