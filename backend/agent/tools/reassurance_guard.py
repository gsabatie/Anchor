"""ADK Tool — intercept and block reassurance patterns in agent output.

Reassurance-seeking is itself a compulsion in OCD. Every reassuring
statement reinforces the obsessive cycle. This guard catches reassuring
language and replaces it with an ERP-appropriate redirect.
"""

from __future__ import annotations

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
    # NOTE: "impossible" removed — too broad for Socratic dialogue context.
    # Covered by targeted regex below.
    # Checking confirmation
    "you already checked",
    "you checked already",
    "you've already checked",
    # NOTE: "it's done" / "it is done" removed — false positives with
    # therapeutic context like "the timer is done". Covered by targeted regex.
    "you did it right",
    "you did it correctly",
    # Implicit reassurance
    "i promise",
    "i guarantee",
    "i assure you",
    "trust me",
    "believe me",
    # NOTE: "absolutely" and "of course" moved to targeted regex patterns
    # to avoid false positives.
    "for sure",
    "one hundred percent",
    "100%",
    "100 percent",
    # -------------------------------------------------------------------
    # French reassurance patterns (projet destiné aux francophones)
    # -------------------------------------------------------------------
    # Direct reassurance — FR
    "ça va aller",
    "ca va aller",
    "tout va bien",
    "tout ira bien",
    "tout va bien se passer",
    "ça ira",
    "ca ira",
    "ça va bien se passer",
    "ca va bien se passer",
    # Worry dismissal — FR
    "t'inquiète pas",
    "ne t'inquiète pas",
    "ne vous inquiétez pas",
    "t'en fais pas",
    "ne t'en fais pas",
    "ne vous en faites pas",
    "tu n'as pas à t'en faire",
    "vous n'avez pas à vous en faire",
    # Safety / danger denial — FR
    "il n'y a pas de danger",
    "y'a pas de danger",
    "il n'y a aucun danger",
    "c'est propre",
    "c'est clean",
    "c'est sûr",
    "c'est sécuritaire",
    "tu es en sécurité",
    "vous êtes en sécurité",
    # Harm denial — FR
    "rien de grave",
    "c'est pas grave",
    "ce n'est pas grave",
    "rien de mal",
    "tu n'as rien fait de mal",
    "vous n'avez rien fait de mal",
    "personne n'a été blessé",
    "personne n'a été blessée",
    "il ne va rien arriver",
    "rien ne va arriver",
    "il ne va rien se passer",
    "rien ne va se passer",
    # Certainty / checking confirmation — FR
    "la porte est fermée",
    "c'est bien fermé",
    "c'est fermé",
    "le four est éteint",
    "c'est éteint",
    "c'est impossible",
    "tu as déjà vérifié",
    "vous avez déjà vérifié",
    "c'est fait",
    "c'est vérifié",
    # Implicit reassurance — FR
    "je te promets",
    "je vous promets",
    "je te garantis",
    "je vous garantis",
    "je t'assure",
    "je vous assure",
    "fais-moi confiance",
    "faites-moi confiance",
    "crois-moi",
    "croyez-moi",
    "bien sûr",
    "évidemment",
    "pas de souci",
    "pas de problème",
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
    # -------------------------------------------------------------------
    # Targeted English patterns (moved from plain-text to reduce false positives)
    # -------------------------------------------------------------------
    # "absolutely" only at sentence start or after punctuation
    re.compile(r"(?:^|[,.!?]\s*)absolutely\b", re.IGNORECASE),
    # "of course" but not when followed by therapeutic-context words
    re.compile(r"\bof course\b(?!\s+(?:the timer|the session|we can|we will|let's))", re.IGNORECASE),
    # "it's done" / "it is done" only when NOT followed by a dash (timer context)
    re.compile(r"\bit(?:'s| is) done\b(?!\s*[—–\-])", re.IGNORECASE),
    # "impossible" only when used as standalone reassurance (not in Socratic questions)
    re.compile(r"(?:^|[,.!?]\s*)(?:that's |that is |it's |it is )?impossible\b(?!\s*(?:\?|to say|to know|to tell))", re.IGNORECASE),
    # -------------------------------------------------------------------
    # French regex patterns
    # -------------------------------------------------------------------
    # "tu es / vous êtes + fine/ok/safe" — FR safety confirmation
    re.compile(r"\b(?:tu es|vous êtes) (?:tout à fait |parfaitement |totalement |complètement )?(?:en sécurité|ok|okay|bien|sauf|sauve|protégé|protégée)\b", re.IGNORECASE),
    # "il n'y a pas / aucun + risque/danger/problème" — FR threat denial
    re.compile(r"\bil (?:n'y a|n'existe) (?:pas de|aucun|pas d') ?(?:risque|danger|problème|souci|menace|mal)\b", re.IGNORECASE),
    # "rien ne peut / va / pourrait arriver / se passer" — FR nothing-will-happen
    re.compile(r"\brien (?:ne )?(?:peut|va|pourrait|pourra) (?:t'|vous )?(?:arriver|se passer)\b", re.IGNORECASE),
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
    # -------------------------------------------------------------------
    # French ERP redirects
    # -------------------------------------------------------------------
    (
        "Je t'entends, et je sais que tu souffres là. "
        "Mais tu sais aussi que si je te rassure, ça ne va pas t'aider vraiment. "
        "On va traverser ça ensemble autrement."
    ),
    (
        "Je comprends que tu veuilles entendre que tout va bien. "
        "Mais te donner cette réponse nourrirait le cycle. "
        "Restons avec l'incertitude ensemble."
    ),
    (
        "Ce que tu me demandes, c'est la compulsion qui parle. "
        "Tu sais que la réponse ne te satisfera pas longtemps. "
        "Dis-moi plutôt, tu es à combien sur 10 ?"
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

    logger.debug("reassurance_guard check: text_length=%d chars", len(output_text))

    matched = _check_patterns(output_text)

    if matched:
        logger.warning("Reassurance pattern blocked: %r", matched)
        return {
            "allowed": False,
            "replacement": _pick_redirect(),
            "matched_pattern": matched,
        }

    return {"allowed": True, "replacement": None, "matched_pattern": None}
