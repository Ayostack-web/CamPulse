from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import get_settings
from app.db_rls import set_current_user_id
from app.security import decode_access_token

logger = logging.getLogger(__name__)
settings = get_settings()

_ACTIVITY_PATHS = {"/api/v1/"}
_ACTIVITY_EXCLUDE = {"/api/v1/health", "/api/v1/ws"}

# Throttle last-active writes: one UPDATE per user per interval, max.
# Per-process state — worst case across N replicas is N writes per interval,
# which the pooled async engine absorbs without connection churn.
_ACTIVITY_WRITE_INTERVAL_SECONDS = 300
_MAX_THROTTLE_ENTRIES = 50_000
_last_activity_write: dict[str, float] = {}


def _should_throttle_write(user_id: str) -> bool:
    now = time.monotonic()
    last = _last_activity_write.get(user_id)
    if last is not None and now - last < _ACTIVITY_WRITE_INTERVAL_SECONDS:
        return True
    if len(_last_activity_write) > _MAX_THROTTLE_ENTRIES:
        cutoff = now - _ACTIVITY_WRITE_INTERVAL_SECONDS
        for uid, ts in list(_last_activity_write.items()):
            if ts < cutoff:
                del _last_activity_write[uid]
    _last_activity_write[user_id] = now
    return False


async def _extract_user_id(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = await decode_access_token(auth[7:])
        return payload.get("sub")
    except Exception:
        return None


class ActivityTrackingMiddleware(BaseHTTPMiddleware):
    """Update user's last_active_at on authenticated API requests.

    Also sets the RLS user context so Postgres row-level security policies
    can enforce per-user access on every database transaction.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        user_id = await _extract_user_id(request)
        set_current_user_id(user_id)
        request.state.user_id = user_id or ""

        try:
            response = await call_next(request)
        finally:
            set_current_user_id(None)

        if user_id and _should_track(request.url.path, request.method):
            if not _should_throttle_write(user_id):
                # Fire-and-forget through the pooled async engine — never
                # blocks the response and no longer opens a raw psycopg
                # connection per request.
                asyncio.create_task(self._update_last_active(user_id))

        return response

    @staticmethod
    async def _update_last_active(user_id: str) -> None:
        try:
            from sqlalchemy import text

            from app.database import async_session

            async with async_session() as db:
                await db.execute(
                    text("UPDATE users SET last_active_at = NOW() WHERE id = :uid"),
                    {"uid": user_id},
                )
                await db.commit()
        except Exception as e:
            logger.debug("Activity tracking skipped: %s", e)


def _should_track(path: str, method: str) -> bool:
    if method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
        return False
    if not any(path.startswith(p) for p in _ACTIVITY_PATHS):
        return False
    if any(path.startswith(p) for p in _ACTIVITY_EXCLUDE):
        return False
    return True
