import logging
import os

from google.cloud import secretmanager

logger = logging.getLogger(__name__)


def get_secret(secret_id: str, version: str = "latest") -> str:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable is not set")

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project}/secrets/{secret_id}/versions/{version}"

    try:
        response = client.access_secret_version(request={"name": name})
    except Exception:
        logger.exception("Failed to access secret '%s'", secret_id)
        raise

    return response.payload.data.decode("utf-8")
