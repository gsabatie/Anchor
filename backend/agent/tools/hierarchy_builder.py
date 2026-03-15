"""ADK Tool — build a personalised 10-level ERP exposure hierarchy."""

import json
import logging
import time
from datetime import datetime, timezone

from google import genai
from google.genai import types

from services.firestore import get_firestore_client

logger = logging.getLogger(__name__)

from config import GEMINI_PRO_MODEL

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
Tu es un spécialiste en thérapie ERP (Exposition avec Prévention de la Réponse) \
pour les TOC (Troubles Obsessionnels Compulsifs).

Le patient décrit son TOC ainsi :
- Type de TOC : {toc_type}
- Description : {toc_description}

Génère une hiérarchie graduée d'exposition de 10 niveaux (1 = le moins anxiogène, \
10 = le plus anxiogène). Chaque niveau doit décrire une situation d'exposition \
concrète, réaliste et spécifique au TOC décrit.

Exemple de niveau bien formulé :
{{ "level": 3, "situation": "Toucher la poignée d'une porte de supermarché avec \
le bout d'un doigt puis ne pas se laver les mains pendant 10 minutes.", \
"anxiety_estimate": 3 }}

Règles :
- Les situations doivent être progressives et cliniquement pertinentes.
- anxiety_estimate peut varier de ±1 par rapport au numéro du niveau.
- Les descriptions doivent être en français, concrètes et concises (1-2 phrases).
- Utilise des références culturelles françaises (transports en commun, pharmacie, \
boulangerie, etc.) plutôt que des références américaines.
- Ne jamais inclure de contenu rassurant dans les descriptions.
- Chaque situation doit impliquer une action spécifique que l'utilisateur peut \
s'imaginer faire, pas juste une peur abstraite.
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

    # --- Check Firestore cache for existing hierarchy ---
    toc_type_normalized = toc_type.strip().lower()
    try:
        db = get_firestore_client()
        existing = (
            db.collection(FIRESTORE_COLLECTION)
            .where("toc_type", "==", toc_type_normalized)
            .order_by("created_at", direction="DESCENDING")
            .limit(1)
            .get()
        )
        if existing:
            doc = existing[0]
            data = doc.to_dict()
            logger.info("Returning cached hierarchy %s for toc_type=%s", doc.id, toc_type_normalized)
            return {"levels": data["levels"], "hierarchy_id": doc.id, "cached": True}
    except Exception as exc:
        logger.warning("Firestore cache lookup failed (non-fatal): %s", exc)

    # --- Generate hierarchy via Gemini Pro with thinking ---
    prompt = _GENERATION_PROMPT.format(
        toc_type=toc_type,
        toc_description=toc_description,
    )

    for attempt in range(MAX_RETRIES):
        try:
            client = _get_client()
            response = client.models.generate_content(
                model=GEMINI_PRO_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                    temperature=0.7,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=4096,
                    ),
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
            "toc_type": toc_type_normalized,
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
