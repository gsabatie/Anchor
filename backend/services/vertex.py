import os

from google.cloud import aiplatform


def init_vertex():
    aiplatform.init(
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("VERTEX_LOCATION", "europe-west1"),
    )
