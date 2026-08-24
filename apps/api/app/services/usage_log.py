"""Per-call AI usage/cost recording.

Every Gemini call site funnels through :func:`record_ai_usage`, which writes
one ``ai_usage`` row (user, plan snapshot, model, tokens, dedup flag, cost
estimate). Best-effort by design: a failed insert must never fail the AI
request it is measuring.

This is the data layer for unit economics — after one exam cycle, pricing
questions (Night Pass size, circuit breakers) become arithmetic instead of
opinion.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from app.core.config import get_settings

logger = logging.getLogger(__name__)

#: How long a resolved user plan is cached in-process. Plan changes are rare;
#: a stale plan on an edge-case row costs nothing analytically.
_PLAN_CACHE_TTL_SECONDS = 300

_plan_cache: dict[str, tuple[float, str]] = {}


def _resolve_plan_sync(conn, user_id: str | None) -> str:
    """Best mirror of entitlement_summary: priciest active pass wins, else free."""
    if not user_id:
        return "system"

    now = time.monotonic()
    cached = _plan_cache.get(user_id)
    if cached is not None and now - cached[0] < _PLAN_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT plan FROM subscriptions
                WHERE user_id = %s AND status = 'active'
                  AND expires_at > NOW() AND quota_total IS NOT NULL
                ORDER BY quota_total DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cursor.fetchone()
    except Exception:
        logger.warning("ai_usage plan lookup failed", exc_info=True)
        return "free"

    plan = row["plan"] if row else "free"
    if len(_plan_cache) > 10_000:
        cutoff = now - _PLAN_CACHE_TTL_SECONDS
        for uid, (ts, _) in list(_plan_cache.items()):
            if ts < cutoff:
                del _plan_cache[uid]
    _plan_cache[user_id] = (now, plan)
    return plan


def record_ai_usage(
    *,
    model: str,
    feature: str,
    user_id: str | None = None,
    task_tier: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    dedup_hit: bool = False,
    est_cost_usd: float = 0.0,
) -> None:
    """Insert one ai_usage row. Never raises."""
    try:
        from app.core.postgres import get_connection

        total = prompt_tokens + completion_tokens
        with get_connection() as conn:
            plan = _resolve_plan_sync(conn, user_id)
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_usage (
                        id, user_id, user_plan, feature, model, task_tier,
                        prompt_tokens, completion_tokens, total_tokens,
                        dedup_hit, est_cost_usd, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        plan,
                        feature,
                        model,
                        task_tier,
                        int(prompt_tokens),
                        int(completion_tokens),
                        int(total),
                        bool(dedup_hit),
                        float(est_cost_usd),
                        datetime.now(timezone.utc),
                    ),
                )
            conn.commit()
    except Exception:
        settings = get_settings()
        if settings.environment == "development":
            logger.warning("ai_usage insert failed", exc_info=True)
        else:
            logger.error("ai_usage insert failed", exc_info=True)
