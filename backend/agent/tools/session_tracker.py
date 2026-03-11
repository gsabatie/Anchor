"""ADK Tool — track ERP sessions in Firestore.

Manages the full lifecycle of an ERP session: starting a new session,
logging individual exposure levels with anxiety data, ending a session,
and retrieving session history for a user.

All data is persisted in Firestore under the configured collection
(default: "sessions").
"""

import logging
import os
import time
import uuid

from google.cloud import firestore

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"start_session", "log_level", "end_session", "get_history"}

REQUIRED_FIELDS = {
    "start_session": {"user_id"},
    "log_level": {"session_id", "level", "anxiety_peak", "resistance"},
    "end_session": {"session_id"},
    "get_history": {"user_id"},
}

_COLLECTION = os.getenv("FIRESTORE_COLLECTION", "sessions")


def _get_db() -> firestore.Client:
    """Return a Firestore client bound to the configured project."""
    return firestore.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT"))


def _start_session(db: firestore.Client, data: dict) -> dict:
    """Create a new ERP session document."""
    session_id = str(uuid.uuid4())
    now = time.time()

    doc = {
        "session_id": session_id,
        "user_id": data["user_id"],
        "started_at": now,
        "ended_at": None,
        "toc_type": data.get("toc_type"),
        "toc_description": data.get("toc_description"),
        "levels": [],
        "status": "active",
    }

    db.collection(_COLLECTION).document(session_id).set(doc)

    logger.info("Session started: id=%s user=%s", session_id, data["user_id"])
    return {"success": True, "session_id": session_id, "started_at": now}


def _log_level(db: firestore.Client, data: dict) -> dict:
    """Append an exposure level entry to an existing session."""
    session_id = data["session_id"]
    doc_ref = db.collection(_COLLECTION).document(session_id)
    doc = doc_ref.get()

    if not doc.exists:
        return {"success": False, "error": f"Session {session_id} not found"}

    session = doc.to_dict()
    if session.get("status") != "active":
        return {"success": False, "error": f"Session {session_id} is not active"}

    level_entry = {
        "level": data["level"],
        "anxiety_peak": data["anxiety_peak"],
        "resistance": data["resistance"],
        "toc_type": data.get("toc_type", session.get("toc_type")),
        "duration_seconds": data.get("duration_seconds"),
        "logged_at": time.time(),
    }

    doc_ref.update({"levels": firestore.ArrayUnion([level_entry])})

    logger.info(
        "Level logged: session=%s level=%d peak=%d resistance=%s",
        session_id, data["level"], data["anxiety_peak"], data["resistance"],
    )
    return {"success": True, "level_entry": level_entry}


def _end_session(db: firestore.Client, data: dict) -> dict:
    """Mark a session as completed."""
    session_id = data["session_id"]
    doc_ref = db.collection(_COLLECTION).document(session_id)
    doc = doc_ref.get()

    if not doc.exists:
        return {"success": False, "error": f"Session {session_id} not found"}

    session = doc.to_dict()
    if session.get("status") != "active":
        return {"success": False, "error": f"Session {session_id} is already ended"}

    now = time.time()
    levels = session.get("levels", [])

    summary = {
        "total_levels": len(levels),
        "max_level": max((l["level"] for l in levels), default=0),
        "max_anxiety_peak": max((l["anxiety_peak"] for l in levels), default=0),
        "resistance_count": sum(1 for l in levels if l.get("resistance")),
        "duration_seconds": now - session["started_at"],
    }

    doc_ref.update({
        "ended_at": now,
        "status": "completed",
        "summary": summary,
    })

    logger.info("Session ended: id=%s summary=%s", session_id, summary)
    return {"success": True, "session_id": session_id, "summary": summary}


def _get_history(db: firestore.Client, data: dict) -> dict:
    """Retrieve past sessions for a user, most recent first."""
    user_id = data["user_id"]
    limit = data.get("limit", 10)

    query = (
        db.collection(_COLLECTION)
        .where("user_id", "==", user_id)
        .order_by("started_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )

    sessions = []
    for doc in query.stream():
        s = doc.to_dict()
        sessions.append({
            "session_id": s["session_id"],
            "started_at": s["started_at"],
            "ended_at": s.get("ended_at"),
            "status": s.get("status"),
            "toc_type": s.get("toc_type"),
            "total_levels": len(s.get("levels", [])),
            "summary": s.get("summary"),
        })

    logger.info("History retrieved: user=%s count=%d", user_id, len(sessions))
    return {"success": True, "user_id": user_id, "sessions": sessions}


_ACTION_HANDLERS = {
    "start_session": _start_session,
    "log_level": _log_level,
    "end_session": _end_session,
    "get_history": _get_history,
}


def session_tracker(action: str, session_data: dict) -> dict:
    """Track ERP sessions in Firestore.

    Manages the lifecycle of exposure therapy sessions — creating,
    logging exposure levels, ending sessions, and retrieving history.

    Args:
        action: One of "start_session", "log_level", "end_session", "get_history".
        session_data: Data payload for the action.
            - start_session: { user_id, toc_type?, toc_description? }
            - log_level: { session_id, level, anxiety_peak, resistance, toc_type?, duration_seconds? }
            - end_session: { session_id }
            - get_history: { user_id, limit? }

    Returns:
        A dict with 'success' (bool) and action-specific data.
    """
    if action not in VALID_ACTIONS:
        return {"success": False, "error": f"Invalid action. Must be one of: {', '.join(sorted(VALID_ACTIONS))}"}

    required = REQUIRED_FIELDS.get(action, set())
    missing = required - set(session_data.keys())
    if missing:
        return {"success": False, "error": f"Missing required fields: {', '.join(sorted(missing))}"}

    try:
        db = _get_db()
        return _ACTION_HANDLERS[action](db, session_data)
    except Exception:
        logger.exception("session_tracker failed: action=%s", action)
        return {"success": False, "error": f"Firestore operation failed for action '{action}'"}
