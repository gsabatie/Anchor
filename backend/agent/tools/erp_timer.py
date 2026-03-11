"""ADK Tool — start an ERP exposure timer with a coaching schedule.

The timer generates a sequence of coaching check-ins calibrated to the
exposure level. Lower levels get gentler, more frequent prompts; higher
levels are more spaced out to let the anxiety wave build and resolve.
The coaching schedule is sent to the frontend which displays prompts at
the right timestamps.
"""

import logging
import time
import uuid

logger = logging.getLogger(__name__)

MIN_DURATION = 1
MAX_DURATION = 120
MIN_LEVEL = 1
MAX_LEVEL = 10

# ---------------------------------------------------------------------------
# Coaching prompts — grouped by phase of the exposure
# ---------------------------------------------------------------------------
_OPENING_PROMPTS = [
    "The timer is running. You're here, and I'm here with you.",
    "We've started. Breathe. Just notice what's happening inside.",
    "The exposure has begun. Whatever you feel right now is valid.",
]

_RISING_PROMPTS = [
    "Where are you on a scale of 0 to 10?",
    "What do you notice in your body right now?",
    "The anxiety may be rising. That's expected. Stay with it.",
    "It's normal for it to climb. The wave has a peak.",
    "You don't have to fight it. Just observe it.",
    "Notice the urge. You don't have to act on it.",
]

_PEAK_PROMPTS = [
    "You're at the peak. This is the hardest part. You're doing it.",
    "This is where it counts. You're holding. Keep going.",
    "The urge is loudest right now. It will pass. Stay with me.",
    "You're riding the wave. It won't stay this high.",
    "This discomfort is temporary. You are not in danger.",
]

_FALLING_PROMPTS = [
    "Notice if anything is shifting. Even a small change counts.",
    "Where are you now, 0 to 10?",
    "Your brain is learning right now. This is the work.",
    "The wave is coming down. You stayed with it.",
    "You're doing something your OCD said you couldn't do.",
]

_CLOSING_PROMPTS = [
    "You rode through it. That's ERP.",
    "The timer is ending. You stayed. That's brave.",
    "You did it. Your brain just learned something important.",
]


def _build_coaching_schedule(level: int, duration_minutes: int) -> list[dict]:
    """Build a list of coaching milestones for the exposure timer.

    The schedule divides the exposure into phases:
    - Opening (0-10%): grounding and initial check-in
    - Rising (10-40%): anxiety climbing, frequent check-ins
    - Peak (40-70%): hardest part, supportive prompts
    - Falling (70-90%): anxiety starting to drop
    - Closing (90-100%): celebration and wrap-up

    Higher levels get slightly fewer prompts to allow the anxiety wave
    to build without interruption.
    """
    total_seconds = duration_minutes * 60

    # More prompts for lower levels, fewer for higher (let the wave build)
    if level <= 3:
        interval_seconds = max(60, total_seconds // 8)
    elif level <= 6:
        interval_seconds = max(90, total_seconds // 6)
    else:
        interval_seconds = max(120, total_seconds // 5)

    schedule = []

    # Phase boundaries as fractions of total time
    phases = [
        (0.0, 0.10, _OPENING_PROMPTS),
        (0.10, 0.40, _RISING_PROMPTS),
        (0.40, 0.70, _PEAK_PROMPTS),
        (0.70, 0.90, _FALLING_PROMPTS),
        (0.90, 1.0, _CLOSING_PROMPTS),
    ]

    phase_names = ["opening", "rising", "peak", "falling", "closing"]

    # Generate prompts at regular intervals, picking from the right phase
    t = interval_seconds
    prompt_index_per_phase = {name: 0 for name in phase_names}

    while t < total_seconds:
        fraction = t / total_seconds

        # Find which phase this timestamp falls in
        for i, (start, end, prompts) in enumerate(phases):
            if start <= fraction < end:
                phase_name = phase_names[i]
                idx = prompt_index_per_phase[phase_name] % len(prompts)
                schedule.append({
                    "offset_seconds": t,
                    "phase": phase_name,
                    "message": prompts[idx],
                })
                prompt_index_per_phase[phase_name] = idx + 1
                break

        t += interval_seconds

    # Always add a closing prompt at the end
    schedule.append({
        "offset_seconds": total_seconds,
        "phase": "closing",
        "message": _CLOSING_PROMPTS[
            prompt_index_per_phase["closing"] % len(_CLOSING_PROMPTS)
        ],
    })

    return schedule


def _recommended_duration(level: int) -> int:
    """Suggest a default duration in minutes based on exposure level."""
    if level <= 2:
        return 10
    if level <= 4:
        return 15
    if level <= 6:
        return 20
    if level <= 8:
        return 30
    return 40


def erp_timer(level: int, duration_minutes: int) -> dict:
    """Start an ERP exposure timer with a coaching schedule.

    Creates a timer for the current exposure level and generates a
    sequence of coaching check-ins calibrated to the level and duration.
    The schedule is returned to the frontend which displays prompts at
    the appropriate timestamps.

    Args:
        level: Current exposure level (1-10).
        duration_minutes: Duration in minutes for this exposure (1-120).

    Returns:
        A dict with 'timer_id', 'started_at', 'duration_seconds',
        'level', and 'coaching_schedule'.
    """
    if not isinstance(level, int) or not (MIN_LEVEL <= level <= MAX_LEVEL):
        return {"error": f"Level must be an integer between {MIN_LEVEL} and {MAX_LEVEL}"}
    if not isinstance(duration_minutes, int) or not (MIN_DURATION <= duration_minutes <= MAX_DURATION):
        return {"error": f"Duration must be an integer between {MIN_DURATION} and {MAX_DURATION} minutes"}

    timer_id = str(uuid.uuid4())
    started_at = time.time()
    duration_seconds = duration_minutes * 60

    schedule = _build_coaching_schedule(level, duration_minutes)

    logger.info(
        "ERP timer started: id=%s level=%d duration=%dm checkpoints=%d",
        timer_id, level, duration_minutes, len(schedule),
    )

    return {
        "timer_id": timer_id,
        "started_at": started_at,
        "duration_seconds": duration_seconds,
        "level": level,
        "recommended_duration": _recommended_duration(level),
        "coaching_schedule": schedule,
    }
