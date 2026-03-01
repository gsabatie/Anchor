import time
import uuid


def erp_timer(level: int, duration_minutes: int) -> dict:
    """Start an ERP exposure timer.

    Args:
        level: Current exposure level (1-10).
        duration_minutes: Duration in minutes for this exposure.

    Returns:
        A dict with 'timer_id' and 'started_at' timestamp.
    """
    # TODO: integrate with WebSocket to send periodic coaching events
    return {
        "timer_id": str(uuid.uuid4()),
        "started_at": time.time(),
    }
