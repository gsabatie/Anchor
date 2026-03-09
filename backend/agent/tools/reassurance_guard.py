REASSURANCE_PATTERNS = [
    "it's going to be okay",
    "everything will be fine",
    "don't worry",
    "there's nothing to worry about",
    "it's clean",
    "it's safe",
    "the door is locked",
    "nothing bad happened",
    "you didn't do anything wrong",
    "there's no danger",
    "it's not a big deal",
    "you're safe",
    "no harm done",
    "i'm sure it's fine",
    "that won't happen",
    "everything is fine",
    "nothing to fear",
    "you have nothing to worry about",
    "it's all good",
]

ERP_REDIRECT = (
    "I hear you, and I know you're hurting right now. "
    "But you also know that if I reassure you, it won't truly help. "
    "Let's work through this together differently."
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
