MAX_DESCRIPTION_LENGTH = 2000


def hierarchy_builder(toc_description: str, toc_type: str) -> dict:
    """Build a 10-level exposure hierarchy for the described OCD.

    Args:
        toc_description: Free-text description of the user's OCD (max 2000 chars).
        toc_type: Category of OCD (e.g. contamination, checking, intrusive thoughts).

    Returns:
        A dict with 'levels': list of {level, situation, anxiety_estimate}.
    """
    if len(toc_description) > MAX_DESCRIPTION_LENGTH:
        return {"error": f"Description too long ({len(toc_description)} chars). Max {MAX_DESCRIPTION_LENGTH}."}

    if not toc_type.strip():
        return {"error": "toc_type is required"}

    # TODO: call Gemini to generate a personalised hierarchy and persist to Firestore
    return {
        "levels": [
            {"level": i, "situation": f"Placeholder situation {i}", "anxiety_estimate": i}
            for i in range(1, 11)
        ]
    }
