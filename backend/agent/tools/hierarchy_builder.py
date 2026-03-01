def hierarchy_builder(toc_description: str, toc_type: str) -> dict:
    """Build a 10-level exposure hierarchy for the described OCD.

    Args:
        toc_description: Free-text description of the user's OCD.
        toc_type: Category of OCD (e.g. contamination, checking, intrusive thoughts).

    Returns:
        A dict with 'levels': list of {level, situation, anxiety_estimate}.
    """
    # TODO: call Gemini to generate a personalised hierarchy and persist to Firestore
    return {
        "levels": [
            {"level": i, "situation": f"Placeholder situation {i}", "anxiety_estimate": i}
            for i in range(1, 11)
        ]
    }
