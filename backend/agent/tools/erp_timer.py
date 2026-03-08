import time
import uuid

MIN_DURATION = 1
MAX_DURATION = 120
MIN_LEVEL = 1
MAX_LEVEL = 10


def erp_timer(level: int, duration_minutes: int) -> dict:
    """Start an ERP exposure timer.

    Args:
        level: Current exposure level (1-10).
        duration_minutes: Duration in minutes for this exposure (1-120).

    Returns:
        A dict with 'timer_id' and 'started_at' timestamp.
    """
    if not (MIN_LEVEL <= level <= MAX_LEVEL):
        return {"error": f"Level must be between {MIN_LEVEL} and {MAX_LEVEL}"}
    if not (MIN_DURATION <= duration_minutes <= MAX_DURATION):
        return {"error": f"Duration must be between {MIN_DURATION} and {MAX_DURATION} minutes"}

    # TODO: integrate with WebSocket to send periodic coaching events
    return {
        "timer_id": str(uuid.uuid4()),
        "started_at": time.time(),
    }
