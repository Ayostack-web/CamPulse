"""Entitlement resolution: who can spend an AI query, and how much vault
storage they're allowed.

The core guarantee is that a query spend is atomic — we only decrement a pass
if it still has remaining capacity (`quota_used < quota_total`), so a hard cap
can never be overspent by concurrent requests.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Material, Subscription
from app import plans


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def active_passes(
    db: AsyncSession, user_id: str, now: datetime | None = None
) -> list[Subscription]:
    now = now or _now()
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.asc())
    )
    return list(result.scalars().all())


async def has_active_paid_pass(db: AsyncSession, user_id: str) -> bool:
    passes = await active_passes(db, user_id)
    return any(p.quota_total for p in passes)


async def spend_paid_query(db: AsyncSession, user_id: str) -> bool:
    """Atomically spend one query from the user's paid passes.

    Spends from the earliest-expiring pass with remaining capacity first so
    nearly-expired quota isn't wasted. Returns True if a query was spent,
    False if the user has paid passes but all are exhausted.
    """
    passes = await active_passes(db, user_id)
    for p in passes:
        if not p.quota_total or p.quota_used >= p.quota_total:
            continue
        result = await db.execute(
            update(Subscription)
            .where(
                Subscription.id == p.id,
                Subscription.quota_used < Subscription.quota_total,
            )
            .values(quota_used=Subscription.quota_used + 1)
        )
        if result.rowcount == 1:
            return True
    return False


async def storage_allowance(db: AsyncSession, user_id: str) -> int:
    """Vault allowance in bytes = free base + the largest active pass grant."""
    passes = await active_passes(db, user_id)
    paid = plans.FREE_STORAGE_BYTES
    for p in passes:
        if p.storage_bytes_total:
            paid = max(paid, p.storage_bytes_total)
    return paid


async def storage_used(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(Material.file_size), 0)).where(
            Material.uploader_id == user_id
        )
    )
    return int(result.scalar_one())


def free_daily_limit(created_at: datetime | None, now: datetime | None = None) -> int:
    now = now or _now()
    if created_at is None:
        return plans.FREE_DAILY_LIMIT
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    if now - created_at <= plans.FIRST_DAY_BOOST_DURATION:
        return plans.FIRST_DAY_BOOST_LIMIT
    return plans.FREE_DAILY_LIMIT


async def entitlement_summary(
    db: AsyncSession,
    user_id: str,
    created_at: datetime | None,
    daily_used: int = 0,
) -> dict:
    """Aggregate entitlement state for the /ai-tokens endpoint.

    ``daily_used`` is the user's free-tier daily counter (used only when the
    user holds no paid pass, or when enforcing the paid daily soft cap).
    """
    now = _now()
    passes = await active_passes(db, user_id)
    paid_passes = [p for p in passes if p.quota_total]

    quota_total = sum(p.quota_total for p in paid_passes)
    quota_used = sum(p.quota_used for p in paid_passes)

    # Resolve the most restrictive daily cap across active paid passes.
    daily_cap = None
    for p in paid_passes:
        if p.plan in plans.PLANS:
            plan_cfg = plans.PLANS[p.plan]
            if plan_cfg.daily_query_cap is not None:
                if daily_cap is None or plan_cfg.daily_query_cap < daily_cap:
                    daily_cap = plan_cfg.daily_query_cap

    if paid_passes:
        plan = max(paid_passes, key=lambda p: p.quota_total).plan
        plan_name = plans.get_plan(plan).name if plan in plans.PLANS else plan
        remaining = max(0, quota_total - quota_used)
        limit = quota_total
        used = quota_used
    else:
        limit = free_daily_limit(created_at, now)
        used = daily_used
        remaining = max(0, limit - daily_used)
        plan = "free"
        plan_name = plans.PLANS["free"].name

    allowance = plans.FREE_STORAGE_BYTES
    for p in passes:
        if p.storage_bytes_total:
            allowance = max(allowance, p.storage_bytes_total)
    used_storage = await storage_used(db, user_id)

    expires = max((p.expires_at for p in paid_passes), default=None)

    return {
        "plan": plan,
        "plan_name": plan_name,
        "quota_total": limit,
        "quota_used": used,
        "quota_remaining": remaining,
        "storage_total_bytes": allowance,
        "storage_used_bytes": used_storage,
        "storage_remaining_bytes": max(0, allowance - used_storage),
        "expires_at": str(expires) if expires else None,
        "has_paid_pass": bool(paid_passes),
        "daily_query_cap": daily_cap,
        "daily_queries_used": daily_used if daily_cap else None,
    }
