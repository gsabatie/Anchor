"""ADK Tool — intercept and block reassurance patterns in agent output.

Reassurance-seeking is itself a compulsion in OCD. Every reassuring
statement reinforces the obsessive cycle. This guard catches reassuring
language and replaces it with an ERP-appropriate redirect.
"""

import logging
import random
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plain-text patterns (checked via substring match, case-insensitive)
# ---------------------------------------------------------------------------
REASSURANCE_PATTERNS = [
    # Direct reassurance
    "it's going to be okay",
    "it is going to be okay",
    "everything will be fine",
    "everything is fine",
    "everything's fine",
    "it's all good",
    "it is all good",
    "it'll be fine",
    "it will be fine",
    "it's fine",
    "it is fine",
    # Worry dismissal
    "don't worry",
    "do not worry",
    "there's nothing to worry about",
    "there is nothing to worry about",
    "you have nothing to worry about",
    "nothing to worry about",
    "nothing to fear",
    "no need to worry",
    "no reason to worry",
    "stop worrying",
    # Safety confirmation
    "it's clean",
    "it is clean",
    "it's safe",
    "it is safe",
    "you're safe",
    "you are safe",
    "the door is locked",
    "the stove is off",
    "it's turned off",
    "it is turned off",
    # Harm denial
    "nothing bad happened",
    "nothing bad will happen",
    "nothing bad is going to happen",
    "you didn't do anything wrong",
    "you did nothing wrong",
    "you haven't done anything wrong",
    "no harm done",
    "no one got hurt",
    "nobody got hurt",
    "there's no danger",
    "there is no danger",
    # Minimization
    "it's not a big deal",
    "it is not a big deal",
    "it's not that bad",
    "it is not that bad",
    "it doesn't matter",
    "it does not matter",
    # Certainty confirmation
    "i'm sure it's fine",
    "i am sure it is fine",
    "that won't happen",
    "that will not happen",
    "that's not going to happen",
    "that can't happen",
    "that cannot happen",
    "there's no way",
    "impossible",
    # Checking confirmation
    "you already checked",
    "you checked already",
    "you've already checked",
    "it's done",
    "it is done",
    "you did it right",
    "you did it correctly",
    # Implicit reassurance
    "i promise",
    "i guarantee",
    "i assure you",
    "trust me",
    "believe me",
    "absolutely",
    "of course",
    "for sure",
    "one hundred percent",
    "100%",
    "100 percent",
]

# ---------------------------------------------------------------------------
# Regex patterns (for variants that substring matching can't catch)
# ---------------------------------------------------------------------------
_REGEX_PATTERNS = [
    # "you're/you are + positive adjective" used as reassurance
    re.compile(r"\byou(?:'re| are) (?:perfectly |totally |completely )?(?:fine|okay|ok|alright|safe)\b", re.IGNORECASE),
    # "there's/there is no + threat word"
    re.compile(r"\bthere(?:'s| is) no (?:risk|threat|danger|problem|issue|harm)\b", re.IGNORECASE),
    # "nothing (bad/wrong) (will/can/is going to) happen"
    re.compile(r"\bnothing (?:bad |wrong )?(?:will|can|could|is going to) happen\b", re.IGNORECASE),
    # "I can confirm/verify that..."
    re.compile(r"\bi can (?:confirm|verify|assure|guarantee)\b", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# ERP redirect responses — rotated for natural conversation
# ---------------------------------------------------------------------------
_ERP_REDIRECTS = [
    (
        "I hear you, and I know you're hurting right now. "
        "But you also know that if I reassure you, it won't truly help. "
        "Let's work through this together differently."
    ),
    (
        "I understand the urge to hear that everything is fine. "
        "But giving you that answer would feed the cycle. "
        "Let's sit with the uncertainty together."
    ),
    (
        "I know you want certainty right now. That's the OCD talking. "
        "The bravest thing you can do is stay with the discomfort. "
        "I'm right here with you."
    ),
    (
        "I hear what you're asking, and I care about you too much to answer it. "
        "Reassurance only makes the OCD stronger. "
        "Let's try something different — what are you feeling in your body right now?"
    ),
    (
        "That question is the compulsion speaking. "
        "You already know the answer won't satisfy you for long. "
        "Let's redirect — tell me, where are you on a scale of 0 to 10?"
    ),
]

# Default redirect (kept for backward compatibility)
ERP_REDIRECT = _ERP_REDIRECTS[0]


def _pick_redirect() -> str:
    """Return a random ERP redirect response."""
    return random.choice(_ERP_REDIRECTS)


def _check_patterns(text: str) -> str | None:
    """Return the first matching pattern found in text, or None."""
    lower = text.lower()

    for pattern in REASSURANCE_PATTERNS:
        if pattern in lower:
            return pattern

    for regex in _REGEX_PATTERNS:
        match = regex.search(text)
        if match:
            return match.group(0)

    return None


def reassurance_guard(output_text: str) -> dict:
    """Check if the agent output contains reassurance patterns and block them.

    This tool intercepts text the agent is about to say and verifies it
    does not contain reassuring language that would reinforce OCD
    compulsions. If a pattern is detected, the text is replaced with an
    ERP-appropriate redirect.

    Args:
        output_text: The text the agent is about to say.

    Returns:
        A dict with:
        - 'allowed' (bool): True if the text is safe to send.
        - 'replacement' (str | None): ERP redirect text if blocked.
        - 'matched_pattern' (str | None): The pattern that triggered the block.
    """
    if not output_text or not output_text.strip():
        return {"allowed": True, "replacement": None, "matched_pattern": None}

    matched = _check_patterns(output_text)

    if matched:
        logger.warning("Reassurance pattern blocked: %r", matched)
        return {
            "allowed": False,
            "replacement": _pick_redirect(),
            "matched_pattern": matched,
        }

    return {"allowed": True, "replacement": None, "matched_pattern": None}
