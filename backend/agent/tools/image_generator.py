import re

MAX_SITUATION_LENGTH = 500


def _sanitize_prompt(text: str) -> str:
    """Strip control characters and limit length for Imagen prompt safety."""
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    return cleaned[:MAX_SITUATION_LENGTH]


def image_generator(situation: str, level: int, toc_type: str) -> dict:
    """Generate an exposure image using Vertex AI Imagen 3.

    Args:
        situation: Description of the exposure situation (max 500 chars).
        level: Exposure level (1-10).
        toc_type: Category of OCD.

    Returns:
        A dict with 'image_url' and 'prompt_used'.
    """
    if not (1 <= level <= 10):
        return {"error": "Level must be between 1 and 10"}

    safe_situation = _sanitize_prompt(situation)
    prompt = f"[level {level}] {safe_situation}"

    # TODO: call Vertex AI Imagen 3 to generate the image and return a signed GCS URL
    return {"image_url": "", "prompt_used": prompt}
