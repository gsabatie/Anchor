"""Centralized configuration — single source of truth for all model IDs and settings."""

import os

# Gemini Live (real-time audio)
GEMINI_LIVE_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-native-audio-latest")

# Gemini text (structured generation — hierarchy builder, etc.)
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")

# Gemini Pro (high-quality generation — hierarchy builder uses thinking mode)
GEMINI_PRO_MODEL = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")

# Vertex AI Imagen 3
IMAGEN_MODEL = os.getenv("IMAGEN_MODEL", "imagen-4.0-generate-001")

# Google Cloud
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "europe-west1")

# Firestore
FIRESTORE_COLLECTION = os.getenv("FIRESTORE_COLLECTION", "sessions")

# API key
GOOGLE_GENAI_API_KEY = os.getenv("GOOGLE_GENAI_API_KEY")
