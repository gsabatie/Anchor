def image_generator(situation: str, level: int, toc_type: str) -> dict:
    """Generate an exposure image using Vertex AI Imagen 3.

    Args:
        situation: Description of the exposure situation.
        level: Exposure level (1-10).
        toc_type: Category of OCD.

    Returns:
        A dict with 'image_url' and 'prompt_used'.
    """
    # TODO: call Vertex AI Imagen 3 to generate the image and return a signed GCS URL
    return {"image_url": "", "prompt_used": f"[level {level}] {situation}"}
