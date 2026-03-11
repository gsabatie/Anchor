"""ADK Tool — generate calibrated exposure images via Vertex AI Imagen 3."""

import base64
import logging
import os
import re

import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

logger = logging.getLogger(__name__)

MAX_SITUATION_LENGTH = 500
MIN_LEVEL = 1
MAX_LEVEL = 10

IMAGEN_MODEL = os.getenv("IMAGEN_MODEL", "imagegeneration@006")

# Calibrate visual intensity per exposure level.
# Lower levels use distant, muted framing; higher levels get close-up and vivid.
_INTENSITY_BANDS = {
    (1, 3): "wide-angle shot, muted pastel colors, calm lighting, the subject is small and distant in the frame",
    (4, 6): "medium shot, natural realistic colors, neutral lighting, the subject is clearly visible",
    (7, 9): "close-up shot, vivid colors, sharp details, the subject fills most of the frame",
    (10, 10): "extreme close-up, hyper-realistic, high detail, the subject dominates the entire frame",
}

_NEGATIVE_PROMPT = (
    "gore, violence, blood, weapons, nudity, sexual content, "
    "text, watermark, logo, cartoon, anime, drawing, painting, "
    "blurry, low quality, distorted faces"
)

_PROMPT_TEMPLATE = """\
Realistic photograph for therapeutic exposure exercise. \
{intensity}. \
Scene: {situation}. \
OCD category context: {toc_type}. \
The image must look like a real everyday photograph, not staged or dramatic.\
"""

_vertexai_initialized = False


def _ensure_vertex_init():
    global _vertexai_initialized
    if not _vertexai_initialized:
        vertexai.init(
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("VERTEX_LOCATION", "europe-west1"),
        )
        _vertexai_initialized = True


def _get_intensity(level: int) -> str:
    for (lo, hi), desc in _INTENSITY_BANDS.items():
        if lo <= level <= hi:
            return desc
    return _INTENSITY_BANDS[(4, 6)]


def _sanitize_prompt(text: str) -> str:
    """Strip control characters and limit length for Imagen prompt safety."""
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
    return cleaned[:MAX_SITUATION_LENGTH]


def _build_prompt(situation: str, level: int, toc_type: str) -> str:
    return _PROMPT_TEMPLATE.format(
        intensity=_get_intensity(level),
        situation=situation,
        toc_type=toc_type,
    )


def image_generator(situation: str, level: int, toc_type: str) -> dict:
    """Generate an exposure image using Vertex AI Imagen 3.

    Produces a realistic photograph calibrated to the exposure level:
    lower levels use distant, muted framing while higher levels are
    close-up and vivid.

    Args:
        situation: Description of the exposure situation (max 500 chars).
        level: Exposure level (1-10).
        toc_type: Category of OCD (e.g. contamination, checking, intrusive thoughts).

    Returns:
        A dict with 'image_base64' (data URI), 'prompt_used', and 'level'.
    """
    if not isinstance(level, int) or not (MIN_LEVEL <= level <= MAX_LEVEL):
        return {"error": f"Level must be an integer between {MIN_LEVEL} and {MAX_LEVEL}"}

    if not situation or not situation.strip():
        return {"error": "situation is required"}

    if not toc_type or not toc_type.strip():
        return {"error": "toc_type is required"}

    safe_situation = _sanitize_prompt(situation)
    prompt = _build_prompt(safe_situation, level, toc_type.strip())

    try:
        _ensure_vertex_init()
        model = ImageGenerationModel.from_pretrained(IMAGEN_MODEL)
        response = model.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="4:3",
            negative_prompt=_NEGATIVE_PROMPT,
            safety_filter_level="block_few",
        )
    except Exception as exc:
        logger.error("Imagen generation failed: %s", exc)
        return {"error": f"Image generation failed: {exc}"}

    if not response.images:
        logger.warning("Imagen returned no images for prompt: %s", prompt[:120])
        return {"error": "Image generation returned no results (possibly blocked by safety filter)"}

    image_bytes = response.images[0]._image_bytes
    b64 = base64.b64encode(image_bytes).decode()
    data_uri = f"data:image/png;base64,{b64}"

    return {
        "image_base64": data_uri,
        "prompt_used": prompt,
        "level": level,
    }
