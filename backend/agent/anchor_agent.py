"""Anchor — ADK Agent for ERP therapy sessions."""

import logging
from copy import deepcopy
from enum import StrEnum
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.genai import types

from agent.prompts.system_prompt import SYSTEM_PROMPT
from agent.tools.erp_timer import erp_timer
from agent.tools.hierarchy_builder import hierarchy_builder
from agent.tools.image_generator import image_generator
from agent.tools.reassurance_guard import reassurance_guard, _check_patterns, _pick_redirect
from agent.tools.session_tracker import session_tracker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ERP session phases
# ---------------------------------------------------------------------------
class ERPPhase(StrEnum):
    INTAKE = "intake"
    HIERARCHY = "hierarchy"
    EXPOSURE = "exposure"
    TIMER = "timer"
    DESCENT = "descent"
    CLOSING = "closing"


SESSION_STATE_DEFAULTS = {
    "current_phase": ERPPhase.INTAKE,
    "current_level": 0,
    "session_id": None,
    "user_id": None,
    "hierarchy": None,
    "anxiety_readings": [],
}


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
def _after_model_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> Optional[LlmResponse]:
    """Intercept every model output and block reassurance patterns."""
    if not llm_response.content or not llm_response.content.parts:
        return None

    # Skip function-call responses (no text to guard)
    first_part = llm_response.content.parts[0]
    if not first_part.text:
        return None

    text = first_part.text
    matched = _check_patterns(text)

    if matched:
        logger.warning(
            "Reassurance pattern blocked by after_model_callback: %r",
            matched,
        )
        modified_parts = [deepcopy(p) for p in llm_response.content.parts]
        modified_parts[0].text = _pick_redirect()
        return LlmResponse(
            content=types.Content(role="model", parts=modified_parts),
            grounding_metadata=llm_response.grounding_metadata,
        )

    return None  # pass through unmodified


# ---------------------------------------------------------------------------
# Dynamic instruction — injects session state into the system prompt
# ---------------------------------------------------------------------------
def _build_instruction(callback_context: CallbackContext) -> str:
    """Return the system prompt augmented with current session context."""
    state = callback_context.state
    phase = state.get("current_phase", ERPPhase.INTAKE)
    level = state.get("current_level", 0)
    readings = state.get("anxiety_readings", [])

    context_block = (
        f"\n\n# CURRENT SESSION CONTEXT\n"
        f"- Phase: {phase}\n"
        f"- Exposure level: {level}/10\n"
        f"- Anxiety readings so far: {readings[-5:] if readings else 'none'}\n"
    )
    return SYSTEM_PROMPT + context_block


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------
anchor_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="anchor",
    description="ERP therapy companion agent for OCD support",
    instruction=_build_instruction,
    tools=[
        reassurance_guard,
        hierarchy_builder,
        image_generator,
        erp_timer,
        session_tracker,
    ],
    after_model_callback=_after_model_callback,
)
