from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    settings = get_settings()
    return {
        "status": "ok",
        "ai": {
            "provider": "gemini",
            "model": "gemini-flash-lite-latest",
            "configured": bool(settings.gemini_api_key),
        },
    }


@router.get("/health/live")
async def liveness():
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness():
    return {"status": "ready"}
