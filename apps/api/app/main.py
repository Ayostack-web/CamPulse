import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.access_log import AccessLogMiddleware
from app.core.middleware import ActivityTrackingMiddleware
from app.routers import (
    health, colleges, courses, topics, user, materials,
    qna, gamification, settings as settings_router, collaboration, maintenance,
    documents, ws, google_drive, study_agent,
    digest, flashcards, payments, plans, solved_bank,
)
from app.services.realtime import start_subscriber

settings = get_settings()
logger = logging.getLogger(__name__)

# ── Structured logging ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)

# ── App ─────────────────────────────────────────────────────────────

if not settings.cors_origin_list:
    print(
        "FATAL: CORS_ORIGINS is not set. Refusing to start with wildcard CORS.",
        file=sys.stderr,
    )
    sys.exit(1)

@asynccontextmanager
async def lifespan(_: FastAPI):
    subscriber_task = asyncio.create_task(start_subscriber())
    yield
    subscriber_task.cancel()


app = FastAPI(title=settings.app_name, version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://[a-zA-Z0-9-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ActivityTrackingMiddleware)
app.add_middleware(AccessLogMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log unhandled errors and return a JSON 500 with a readable detail."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error ({type(exc).__name__}: {exc})"},
    )

# Core routers
app.include_router(health.router)
app.include_router(colleges.router, prefix=settings.api_prefix)
app.include_router(courses.router, prefix=settings.api_prefix)
app.include_router(topics.router, prefix=settings.api_prefix)
app.include_router(user.router, prefix=settings.api_prefix)
app.include_router(materials.router, prefix=settings.api_prefix)
app.include_router(qna.router, prefix=settings.api_prefix)
app.include_router(gamification.router, prefix=settings.api_prefix)
app.include_router(settings_router.router, prefix=settings.api_prefix)
app.include_router(collaboration.router, prefix=settings.api_prefix)
app.include_router(maintenance.router, prefix=settings.api_prefix)
app.include_router(google_drive.router, prefix=settings.api_prefix)

# Study Agent router
app.include_router(study_agent.router, prefix=settings.api_prefix)

# AI/ML routers (from python-service)
app.include_router(documents.router, prefix=settings.api_prefix)

# WebSocket
app.include_router(ws.router)

# Retention & Digest
app.include_router(digest.router, prefix=settings.api_prefix)

# Flashcards
app.include_router(flashcards.router, prefix=settings.api_prefix)

# Payments
app.include_router(payments.router, prefix=settings.api_prefix)

# Public pricing plans
app.include_router(plans.router, prefix=settings.api_prefix)

# Solved Question Bank
app.include_router(solved_bank.router, prefix=settings.api_prefix)
