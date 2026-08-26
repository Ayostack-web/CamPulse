from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database import get_db
from app.entitlements import (
    free_daily_limit,
    has_active_paid_pass,
    spend_paid_query,
)
from app.models import User, UserEmail
from app.security import decode_access_token
from app.services.points import maybe_activate_referral

logger = logging.getLogger(__name__)
settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

# West Africa Time (UTC+1) — Nigerian students expect daily resets at midnight WAT.
WAT = timezone(timedelta(hours=1))


class RateLimiter:
    """In-memory sliding window rate limiter (fallback when Redis is unavailable)."""

    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_rate_limited(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]
        if len(self._requests[key]) >= self.max_requests:
            return True
        self._requests[key].append(now)
        return False


ai_rate_limiter = RateLimiter(max_requests=15, window_seconds=60)
anonymous_ip_limiter = RateLimiter(max_requests=30, window_seconds=60)
payment_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

# Redis fixed-window limiter so the limit holds across replicas. Falls back
# to the per-process limiter above whenever Redis is unreachable.
_rate_limit_redis: aioredis.Redis | None = None


def _get_rate_limit_redis() -> aioredis.Redis:
    global _rate_limit_redis
    if _rate_limit_redis is None:
        _rate_limit_redis = aioredis.from_url(
            settings.redis_url, decode_responses=True, socket_timeout=1
        )
    return _rate_limit_redis


async def _redis_rate_limited(
    key: str, max_requests: int, window_seconds: int
) -> bool | None:
    """Fixed-window counter (INCR + EXPIRE) shared across replicas.

    Returns True/False for a verdict, or None when Redis is unavailable so
    the caller can fall back to the in-process limiter.
    """
    try:
        client = _get_rate_limit_redis()
        bucket = int(time.time()) // window_seconds
        rkey = f"rl:{key}:{bucket}"
        count = await client.incr(rkey)
        if count == 1:
            await client.expire(rkey, window_seconds + 1)
        return count > max_requests
    except Exception as exc:
        logger.debug("Redis rate limiter unavailable (%s); using in-memory fallback", exc)
        return None


@dataclass
class CurrentUser:
    id: str
    email: str | None
    full_name: str | None
    user: User
async def _decode_jwt_payload(token: str) -> dict:
    return await decode_access_token(token)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    payload = await _decode_jwt_payload(token)

    supabase_user_id = payload.get("sub")
    email = payload.get("email")

    if not supabase_user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == supabase_user_id))
    user = result.scalar_one_or_none()

    if not user:
        # Auto-create user from JWT (onboarding flow)
        user = User(
            id=supabase_user_id,
            full_name=payload.get("user_metadata", {}).get("full_name", email or "User"),
        )
        db.add(user)
        await db.flush()

        if email:
            user_email = UserEmail(email=email, user_id=user.id, is_primary=True, is_verified=True)
            db.add(user_email)
            await db.flush()

    return CurrentUser(id=user.id, email=email, full_name=user.full_name, user=user)


async def spend_ai_query(current_user: CurrentUser, db: AsyncSession) -> None:
    """Spend one AI query from the user's entitlements.

    Order of preference:
      1. A paid pass with remaining capacity (atomic spend — hard cap).
         Long-duration plans (semester, session) enforce a daily soft cap
         to spread usage across the subscription window.
      2. The free daily counter (5/day, 10 on the first day).

    A user who holds paid passes but has exhausted all of them gets a hard
    stop — they need a Top-Up, not a fresh free daily reset.

    Callable mid-handler for endpoints that should only charge once they
    know an AI call will actually happen (e.g. document chat skips the
    charge when retrieval finds nothing).
    """
    from app.entitlements import active_passes as _active_passes
    from app import plans as plans_mod

    u = current_user.user
    now = datetime.now(timezone.utc)

    if await has_active_paid_pass(db, u.id):
        # ── Daily soft cap for long-duration plans ──────────────────────
        # Resolve the most restrictive daily cap across active paid passes.
        passes = await _active_passes(db, u.id)
        daily_cap = None
        for p in passes:
            if p.quota_total and p.plan in plans_mod.PLANS:
                plan_cfg = plans_mod.PLANS[p.plan]
                if plan_cfg.daily_query_cap is not None:
                    if daily_cap is None or plan_cfg.daily_query_cap < daily_cap:
                        daily_cap = plan_cfg.daily_query_cap

        if daily_cap is not None:
            today_wat = now.astimezone(WAT).date()
            reset_wat = u.daily_tokens_reset_at.astimezone(WAT).date() if u.daily_tokens_reset_at else None
            if reset_wat is None or reset_wat < today_wat:
                u.daily_tokens_used = 0
                u.daily_tokens_reset_at = now

            if u.daily_tokens_used >= daily_cap:
                raise HTTPException(
                    status_code=429,
                    detail="DAILY_LIMIT_REACHED",
                    headers={
                        "X-Tokens-Reset": "midnight",
                        "X-Quota-Scope": "paid-daily-cap",
                        "X-Daily-Cap": str(daily_cap),
                    },
                )
            u.daily_tokens_used += 1
            u.daily_tokens_reset_at = now

        if not await spend_paid_query(db, u.id):
            raise HTTPException(
                status_code=429,
                detail="DAILY_LIMIT_REACHED",
                headers={"X-Tokens-Reset": "midnight", "X-Quota-Scope": "paid-pool"},
            )
        await maybe_activate_referral(db, u.id)
        await db.flush()
        return

    today_wat = now.astimezone(WAT).date()
    reset_wat = u.daily_tokens_reset_at.astimezone(WAT).date() if u.daily_tokens_reset_at else None
    if reset_wat is None or reset_wat < today_wat:
        u.daily_tokens_used = 0
        u.daily_tokens_reset_at = now

    limit = free_daily_limit(u.created_at, now)
    if u.daily_tokens_used >= limit:
        raise HTTPException(
            status_code=429,
            detail="DAILY_LIMIT_REACHED",
            headers={"X-Tokens-Reset": "midnight", "X-Quota-Scope": "free-daily"},
        )

    u.daily_tokens_used += 1
    u.daily_tokens_reset_at = now
    await maybe_activate_referral(db, u.id)
    await db.flush()


async def check_ai_token_quota(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """FastAPI dependency: authenticate then spend one AI query up front."""
    await spend_ai_query(current_user, db)
    return current_user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser | None:
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


async def check_ai_rate_limit(
    request: Request,
    user: CurrentUser | None = Depends(get_optional_user),
) -> None:
    """Dependency that enforces rate limiting on AI endpoints.

    Keyed by user ID for authenticated students so a whole class sharing one
    campus NAT/IP never shares a single bucket. Anonymous traffic falls back
    to a per-IP guard. Counting lives in Redis so the limit survives
    horizontal scaling; if Redis is down, the per-process sliding window
    still bounds abuse.
    """
    if user is not None:
        key = f"ai:user:{user.id}"
        limiter = ai_rate_limiter
    else:
        key = f"ai:ip:{request.client.host if request.client else 'unknown'}"
        limiter = anonymous_ip_limiter

    limited = await _redis_rate_limited(key, limiter.max_requests, limiter.window_seconds)
    if limited is None:
        limited = limiter.is_rate_limited(key)
    if limited:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment before trying again.",
        )


async def check_payment_rate_limit(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Burst guard on payment endpoints — each verify call hits Monnify's API.

    Keyed by user ID in Redis so the limit holds across replicas; falls back
    to the per-process limiter when Redis is unreachable.
    """
    key = f"pay:user:{user.id}"
    limited = await _redis_rate_limited(
        key, payment_rate_limiter.max_requests, payment_rate_limiter.window_seconds
    )
    if limited is None:
        limited = payment_rate_limiter.is_rate_limited(key)
    if limited:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment before trying again.",
        )
    return user


async def verify_maintenance_key(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    x_key = request.headers.get("x-maintenance-key", "")

    key = ""
    if auth_header.startswith("Bearer "):
        key = auth_header[7:]
    elif x_key:
        key = x_key

    if not settings.maintenance_api_key:
        raise HTTPException(status_code=503, detail="Maintenance mode not configured")
    if key != settings.maintenance_api_key:
        raise HTTPException(status_code=403, detail="Invalid maintenance key")
    return key
