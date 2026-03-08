VALID_ACTIONS = {"start_session", "log_level", "end_session", "get_history"}

REQUIRED_FIELDS = {
    "start_session": {"user_id"},
    "log_level": {"session_id", "level", "anxiety_peak", "resistance"},
    "end_session": {"session_id"},
    "get_history": {"user_id"},
}


def session_tracker(action: str, session_data: dict) -> dict:
    """Track ERP sessions in Firestore.

    Args:
        action: One of "start_session", "log_level", "end_session", "get_history".
        session_data: Data payload for the action.

    Returns:
        A dict with 'success' (bool).
    """
    if action not in VALID_ACTIONS:
        return {"success": False, "error": f"Invalid action. Must be one of: {', '.join(sorted(VALID_ACTIONS))}"}

    required = REQUIRED_FIELDS.get(action, set())
    missing = required - set(session_data.keys())
    if missing:
        return {"success": False, "error": f"Missing required fields: {', '.join(sorted(missing))}"}

    # TODO: implement Firestore CRUD on the "sessions" collection
    return {"success": True}
