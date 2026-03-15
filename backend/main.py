import logging
import os

from dotenv import load_dotenv

# load_dotenv MUST run before any module that reads env vars via config.py
load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.routes import router  # noqa: E402
from api.websocket import ws_router  # noqa: E402

# ---------------------------------------------------------------------------
# Logging configuration — structured format with module name for traceability
# ---------------------------------------------------------------------------
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

is_production = os.getenv("ENV") == "production"

app = FastAPI(
    title="Anchor",
    description="ERP Therapy Companion Agent",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(router, prefix="/api")
app.include_router(ws_router)

# ---------------------------------------------------------------------------
# Startup summary — key config (no secrets)
# ---------------------------------------------------------------------------
logger.info("Anchor backend starting up")
logger.info(
    "Config: ENV=%s, LOG_LEVEL=%s, REGION=%s",
    os.getenv("ENV", "development"),
    log_level,
    os.getenv("GOOGLE_CLOUD_REGION", "not set"),
)
logger.info(
    "Models: GEMINI_LIVE=%s, GEMINI_PRO=%s, IMAGEN=%s",
    os.getenv("GEMINI_MODEL", "not set"),
    os.getenv("GEMINI_PRO_MODEL", "not set"),
    os.getenv("IMAGEN_MODEL", "not set"),
)
logger.info(
    "Services: FRONTEND_URL=%s, FIRESTORE_COLLECTION=%s, VERTEX_LOCATION=%s",
    os.getenv("FRONTEND_URL", "http://localhost:5173"),
    os.getenv("FIRESTORE_COLLECTION", "sessions"),
    os.getenv("VERTEX_LOCATION", "europe-west1"),
)
logger.info(
    "Docs UI: %s",
    "disabled (production)" if is_production else "enabled at /docs and /redoc",
)
