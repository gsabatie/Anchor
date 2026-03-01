import os

from google.cloud import secretmanager


def get_secret(secret_id: str, version: str = "latest") -> str:
    client = secretmanager.SecretManagerServiceClient()
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    name = f"projects/{project}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")
