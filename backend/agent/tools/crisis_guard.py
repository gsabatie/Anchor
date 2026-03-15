"""ADK Tool -- detect crisis language and redirect to emergency services.

This is a SAFETY-CRITICAL guard. When a user expresses suicidal ideation,
self-harm intent, or severe psychological crisis, the system must immediately
redirect them to the 3114 (France's national suicide prevention hotline).

Unlike the reassurance_guard (which rotates responses for natural conversation),
this guard uses a single, consistent crisis redirect message. Predictability
and clarity are paramount in a crisis.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Crisis redirect -- single, deterministic response (no rotation)
# ---------------------------------------------------------------------------
CRISIS_REDIRECT = (
    "Ce que tu traverses dépasse ce que je peux t'offrir seul. "
    "S'il te plaît, appelle le 3114 maintenant — c'est le numéro national de prévention du suicide, "
    "disponible 24h/24. Ils peuvent t'aider. "
    "Je reste là, mais c'est important que tu appelles."
)

# ---------------------------------------------------------------------------
# French crisis patterns (case-insensitive substring matching)
# ---------------------------------------------------------------------------
CRISIS_PATTERNS_FR = [
    # Suicidal ideation
    "je veux mourir",
    "je veux en finir",
    "j'en peux plus",
    "je vais me tuer",
    "je vais me suicider",
    "je pense au suicide",
    "je pense à me tuer",
    # Self-harm
    "je veux me faire du mal",
    "je veux me blesser",
    # Hopelessness
    "la vie ne vaut pas la peine",
    "la vie n'a pas de sens",
    "je serais mieux mort",
    "je serais mieux morte",
    # Isolation / burden
    "plus personne ne me regrettera",
    "personne ne me regrettera",
    # No reason to live
    "je n'ai plus de raison de vivre",
    "aucune raison de vivre",
    # Disappearance / stopping
    "je veux disparaître",
    "je veux tout arrêter",
    # Active planning
    "j'ai un plan pour en finir",
    # Past self-harm
    "je me suis fait du mal",
    "je me suis coupé",
    "je me suis coupée",
    "je me suis blessé",
    "je me suis blessée",
]

# ---------------------------------------------------------------------------
# English crisis patterns (case-insensitive substring matching)
# ---------------------------------------------------------------------------
CRISIS_PATTERNS_EN = [
    # Suicidal ideation
    "i want to die",
    "i want to end it",
    "i can't take it anymore",
    "i'm going to kill myself",
    "i am going to kill myself",
    "i'm thinking about suicide",
    "thinking about killing myself",
    # Self-harm
    "i want to hurt myself",
    "i want to harm myself",
    # Hopelessness
    "life isn't worth living",
    "life has no meaning",
    "i'd be better off dead",
    "everyone would be better off",
    # Isolation / burden
    "no one would miss me",
    "nobody would care",
    # No reason to live
    "i have no reason to live",
    "no reason to go on",
    # Disappearance / stopping
    "i want to disappear",
    "i want it all to stop",
    # Active planning
    "i have a plan to end it",
    # Past self-harm
    "i've been hurting myself",
    "i've been cutting",
]

CRISIS_PATTERNS = CRISIS_PATTERNS_FR + CRISIS_PATTERNS_EN

# ---------------------------------------------------------------------------
# Regex patterns (catch grammatical variants that substring matching misses)
# ---------------------------------------------------------------------------
_REGEX_PATTERNS = [
    # French: "je veux/voudrais/vais (me) tuer/suicider/en finir"
    re.compile(
        r"\bje (?:veux|voudrais|vais) (?:me )?(?:tuer|suicider|en finir)\b",
        re.IGNORECASE,
    ),
    # English: "i want/need/going to die/end it/kill myself"
    re.compile(
        r"\bi (?:want|need|going) to (?:die|end it|kill myself)\b",
        re.IGNORECASE,
    ),
    # Standalone keywords in any language
    re.compile(
        r"\b(?:suicide|suicidal|self[- ]harm)\b",
        re.IGNORECASE,
    ),
]


def _check_crisis_patterns(text: str) -> str | None:
    """Return the first matching crisis pattern found in *text*, or ``None``.

    Checks plain-text substring patterns first (fast path), then falls back
    to regex patterns for variant matching.
    """
    lower = text.lower()

    for pattern in CRISIS_PATTERNS:
        if pattern in lower:
            return pattern

    for regex in _REGEX_PATTERNS:
        match = regex.search(text)
        if match:
            return match.group(0)

    return None


def crisis_guard(text: str) -> dict:
    """Check if *text* contains crisis language requiring emergency redirect.

    This guard analyses user speech (transcribed text) for indicators of
    suicidal ideation, self-harm intent, or severe psychological crisis.
    When a pattern is detected the caller must surface the redirect message
    to the user immediately.

    Args:
        text: The user's transcribed speech or typed message.

    Returns:
        A dict with:
        - ``crisis_detected`` (bool): ``True`` if crisis language was found.
        - ``redirect`` (str | None): The crisis redirect message, or ``None``.
        - ``matched_pattern`` (str | None): The pattern that triggered detection.
    """
    if not text or not text.strip():
        return {"crisis_detected": False, "redirect": None, "matched_pattern": None}

    matched = _check_crisis_patterns(text)

    if matched:
        logger.critical("CRISIS language detected: %r", matched)
        return {
            "crisis_detected": True,
            "redirect": CRISIS_REDIRECT,
            "matched_pattern": matched,
        }

    return {"crisis_detected": False, "redirect": None, "matched_pattern": None}
