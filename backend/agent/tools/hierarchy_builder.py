"""ADK Tool — build a personalised 10-level ERP exposure hierarchy."""

import json
import logging
import time
from datetime import datetime, timezone

from google import genai
from google.genai import types

from services.firestore import get_firestore_client

logger = logging.getLogger(__name__)

from config import GEMINI_TEXT_MODEL

MAX_DESCRIPTION_LENGTH = 2000
FIRESTORE_COLLECTION = "hierarchies"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds

_genai_client = None


def _get_client():
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client()
    return _genai_client

_GENERATION_PROMPT = """\
You are an ERP (Exposure and Response Prevention) therapy specialist \
for OCD (Obsessive-Compulsive Disorder).

The patient describes their OCD as follows:
- OCD type: {toc_type}
- Description: {toc_description}

Generate a graduated exposure hierarchy of 10 levels (1 = least anxiety-inducing, \
10 = most anxiety-inducing). Each level must describe a concrete, realistic \
exposure situation specific to the described OCD.

Rules:
- Situations must be progressive and clinically relevant.
- anxiety_estimate must match the level number.
- Descriptions must be in French, concise (1-2 sentences).
- Never include reassuring content in the descriptions.
"""

_LEVEL_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "level": types.Schema(type=types.Type.INTEGER),
        "situation": types.Schema(type=types.Type.STRING),
        "anxiety_estimate": types.Schema(type=types.Type.INTEGER),
    },
    required=["level", "situation", "anxiety_estimate"],
)

_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.ARRAY,
    items=_LEVEL_SCHEMA,
)


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

    # --- Generate hierarchy via Gemini ---
    prompt = _GENERATION_PROMPT.format(
        toc_type=toc_type,
        toc_description=toc_description,
    )

    for attempt in range(MAX_RETRIES):
        try:
            client = _get_client()
            response = client.models.generate_content(
                model=GEMINI_TEXT_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                    temperature=0.7,
                    safety_settings=[
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                        ),
                    ],
                ),
            )
            levels = json.loads(response.text)
            break
        except Exception as exc:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("Gemini call failed (attempt %d/%d), retrying in %.1fs: %s", attempt + 1, MAX_RETRIES, delay, exc)
                time.sleep(delay)
            else:
                logger.error("Gemini hierarchy generation failed after %d attempts: %s", MAX_RETRIES, exc)
                return {"error": f"Failed to generate hierarchy: {exc}"}

    if not isinstance(levels, list) or len(levels) != 10:
        return {"error": f"Expected 10 levels from Gemini, got {len(levels) if isinstance(levels, list) else type(levels).__name__}"}

    # Ensure levels are sorted by level number
    levels.sort(key=lambda l: l["level"])

    # --- Persist to Firestore ---
    hierarchy_id = None
    try:
        db = get_firestore_client()
        doc_ref = db.collection(FIRESTORE_COLLECTION).document()
        doc_ref.set({
            "toc_type": toc_type,
            "toc_description": toc_description,
            "levels": levels,
            "created_at": datetime.now(timezone.utc),
        })
        hierarchy_id = doc_ref.id
    except Exception as exc:
        logger.warning("Firestore persistence failed (non-fatal): %s", exc)

    result = {"levels": levels}
    if hierarchy_id:
        result["hierarchy_id"] = hierarchy_id
    return result
