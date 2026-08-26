import time

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.database import async_session

router = APIRouter(tags=["health"])


async def _check_db() -> dict:
    try:
        start = time.monotonic()
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


async def _check_redis() -> dict:
    try:
        import redis.asyncio as aioredis
        settings = get_settings()
        client = aioredis.from_url(settings.redis_url, socket_timeout=2)
        start = time.monotonic()
        await client.ping()
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        await client.aclose()
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


@router.get("/health")
async def health_check():
    settings = get_settings()
    db = await _check_db()
    redis = await _check_redis()
    all_ok = db["status"] == "ok" and redis["status"] == "ok"
    return {
        "status": "ok" if all_ok else "degraded",
        "ai": {
            "provider": "gemini",
            "model": "gemini-flash-lite-latest",
            "configured": bool(settings.gemini_api_key),
        },
        "db": db,
        "redis": redis,
    }


@router.get("/health/live")
async def liveness():
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness():
    """Readiness probe: fails if DB or Redis are unreachable."""
    db = await _check_db()
    redis = await _check_redis()
    if db["status"] != "ok" or redis["status"] != "ok":
        return {"status": "not_ready", "db": db, "redis": redis}
    return {"status": "ready"}
