REASSURANCE_PATTERNS = [
    "ça va aller",
    "t'inquiète pas",
    "ne t'inquiète pas",
    "c'est propre",
    "c'est sûr",
    "c'est bien fermé",
    "il ne s'est rien passé",
    "tu n'as rien fait de mal",
    "tout va bien",
    "il n'y a pas de danger",
    "c'est pas grave",
    "rien de mal",
]

ERP_REDIRECT = (
    "Je t'entends, et je sais que tu souffres là. "
    "Mais tu sais aussi que si je te rassure, ça ne va pas t'aider vraiment. "
    "On va traverser ça ensemble autrement."
)


def reassurance_guard(output_text: str) -> dict:
    """Check if the agent output contains reassurance patterns and block them.

    Args:
        output_text: The text the agent is about to say.

    Returns:
        A dict with 'allowed' (bool) and optionally 'replacement' (str).
    """
    lower = output_text.lower()
    for pattern in REASSURANCE_PATTERNS:
        if pattern in lower:
            return {"allowed": False, "replacement": ERP_REDIRECT}
    return {"allowed": True, "replacement": None}
