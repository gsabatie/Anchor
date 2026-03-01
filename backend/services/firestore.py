import os

from google.cloud import firestore


def get_firestore_client() -> firestore.Client:
    return firestore.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT"))
