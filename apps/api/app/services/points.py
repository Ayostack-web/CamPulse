"""Study Points: the single policy layer for earning and spending points.

Points are a marketing liability, not a currency, so every rule that bounds
that liability lives here:

- Earning goes through :func:`award`, which clamps to a weekly earn cap.
- Spending reads only the rolling window (``points_expiry_days``), so old
  points expire without any sweep job.
- Redemption converts points into an AI-query Subscription pass via the
  existing entitlement machinery (atomic quota spend in app.entitlements).

No schema changes: RewardItem rows are seeded idempotently from
REWARD_CATALOG, redemptions are ledgered as negative PointsTransactions,
and the resulting pass is a plain Subscription row (plan="reward_pass").
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    PointsTransaction, Referral, RewardItem, Subscription, User,
    UserRewardPurchase,
)

REASON_CHECK_IN = "daily_login"
REASON_REFERRAL_WELCOME = "referral_welcome"
REASON_REFERRAL_ACTIVATED = "referral_activation_bonus"
REASON_REFERRAL_UNLOCK = "referral_unlock"
REASON_PQ_UPLOAD = "pq_upload"
REASON_PQ_MILESTONE = "pq_milestone"
REASON_REDEMPTION = "reward_redemption"

# Legacy reason kept for totals: referrals claimed before activation gating
# paid both sides immediately under this label.
REFERRAL_INVITER_REASONS = ("referral_bonus", REASON_REFERRAL_ACTIVATED)

REFERRER_REWARD = 100
REFEREE_REWARD = 50

PQ_UPLOAD_POINTS = 5
PQ_MILESTONE_EVERY = 10
PQ_MILESTONE_POINTS = 50


REWARD_CATALOG: list[dict] = [
    {
        "code": "ai_queries_25",
        "name": "25 AI Queries",
        "description": "Turn your study points into 25 AI tutor questions. Valid for 60 days.",
        "category": "ai_queries",
        "points_cost": 100,
        "query_quota": 25,
        "duration_days": 60,
    },
    {
        "code": "ai_queries_75",
        "name": "75 AI Queries",
        "description": "Best value: 75 AI tutor questions from study points. Valid for 90 days.",
        "category": "ai_queries",
        "points_cost": 250,
        "query_quota": 75,
        "duration_days": 90,
    },
]

REWARD_PASS_PLAN = "reward_pass"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def spendable_balance(db: AsyncSession, user_id: str) -> int:
    settings = get_settings()
    cutoff = _now() - timedelta(days=settings.points_expiry_days)
    result = await db.execute(
        select(func.coalesce(func.sum(PointsTransaction.amount), 0)).where(
            PointsTransaction.user_id == user_id,
            PointsTransaction.created_at >= cutoff,
        )
    )
    return int(result.scalar_one())


async def earned_since(db: AsyncSession, user_id: str, days: float) -> int:
    cutoff = _now() - timedelta(days=days)
    result = await db.execute(
        select(func.coalesce(func.sum(PointsTransaction.amount), 0)).where(
            PointsTransaction.user_id == user_id,
            PointsTransaction.amount > 0,
            PointsTransaction.created_at >= cutoff,
        )
    )
    return int(result.scalar_one())


async def award(
    db: AsyncSession,
    user_id: str,
    amount: int,
    reason: str,
    description: str | None = None,
    related_id: str | None = None,
) -> int:
    """Credit points up to the remaining weekly earn cap.

    Returns the amount actually credited (0 when the cap is exhausted).
    contribution_score mirrors credited points so leaderboards stay honest.
    """
    if amount <= 0:
        return 0
    settings = get_settings()
    earned = await earned_since(db, user_id, days=7)
    allowed = max(0, settings.points_weekly_earn_cap - earned)
    credited = min(amount, allowed)
    if credited <= 0:
        return 0
    db.add(PointsTransaction(
        user_id=user_id,
        amount=credited,
        reason=reason,
        description=description,
        related_id=related_id,
    ))
    user = await db.get(User, user_id)
    if user:
        user.contribution_score += credited
    return credited


async def has_reason_transaction(
    db: AsyncSession, user_id: str, reason: str, related_id: str | None = None
) -> bool:
    query = select(PointsTransaction.id).where(
        PointsTransaction.user_id == user_id,
        PointsTransaction.reason == reason,
    )
    if related_id is not None:
        query = query.where(PointsTransaction.related_id == related_id)
    result = await db.execute(query.limit(1))
    return result.first() is not None


async def ensure_reward_items(db: AsyncSession) -> list[RewardItem]:
    existing = await db.execute(
        select(RewardItem).where(RewardItem.is_active == True)  # noqa: E712
    )
    items = {i.code: i for i in existing.scalars().all()}
    created_any = False
    for spec in REWARD_CATALOG:
        if spec["code"] not in items:
            item = RewardItem(
                code=spec["code"],
                name=spec["name"],
                description=spec["description"],
                points_cost=spec["points_cost"],
                category=spec["category"],
                is_active=True,
            )
            db.add(item)
            items[spec["code"]] = item
            created_any = True
    if created_any:
        await db.flush()
    return [items[spec["code"]] for spec in REWARD_CATALOG]


def reward_spec(code: str) -> dict | None:
    for spec in REWARD_CATALOG:
        if spec["code"] == code:
            return spec
    return None


async def redeem_reward(db: AsyncSession, user_id: str, code: str) -> dict:
    """Spend points on a catalog reward and mint an AI-query pass.

    One transaction does everything: balance check, negative ledger entry,
    purchase receipt, and the Subscription pass. The reference derives from
    the purchase id so a retried request can never double-mint a pass.
    """
    spec = reward_spec(code)
    if spec is None:
        raise ValueError("unknown_reward")

    balance = await spendable_balance(db, user_id)
    if balance < spec["points_cost"]:
        raise ValueError("insufficient_points")

    purchase = UserRewardPurchase(
        user_id=user_id,
        reward_id=str(uuid.uuid4()),
        code=f"VYR-{uuid.uuid4().hex[:10].upper()}",
        expires_at=_now() + timedelta(days=spec["duration_days"]),
    )
    db.add(purchase)
    await db.flush()

    db.add(PointsTransaction(
        user_id=user_id,
        amount=-spec["points_cost"],
        reason=REASON_REDEMPTION,
        description=f"Redeemed: {spec['name']}",
        related_id=purchase.id,
    ))

    subscription = Subscription(
        user_id=user_id,
        reference=f"REWARD-{purchase.id}",
        plan=REWARD_PASS_PLAN,
        status="active",
        expires_at=purchase.expires_at,
        quota_total=spec["query_quota"],
        quota_used=0,
        storage_bytes_total=0,
        storage_bytes_used=0,
    )
    db.add(subscription)
    await db.flush()

    return {
        "reward_code": spec["code"],
        "name": spec["name"],
        "points_spent": spec["points_cost"],
        "queries_granted": spec["query_quota"],
        "purchase_id": purchase.id,
        "expires_at": purchase.expires_at,
        "balance_after": await spendable_balance(db, user_id),
    }


async def maybe_activate_referral(db: AsyncSession, referee_id: str) -> bool:
    """Pay the referrer once their invitee spends a first AI query.

    Called from the AI-spend path. Cheap for the common case: a single
    indexed lookup that finds no referral row for non-referred users.
    """
    referral = (
        await db.execute(select(Referral).where(Referral.referee_id == referee_id))
    ).scalar_one_or_none()
    if referral is None:
        return False

    already_paid = await has_reason_transaction(
        db, referral.referrer_id, REASON_REFERRAL_ACTIVATED, related_id=referral.id
    )
    if already_paid:
        return False

    awarded = await award(
        db,
        referral.referrer_id,
        REFERRER_REWARD,
        REASON_REFERRAL_ACTIVATED,
        description="Your invite completed their first AI question",
        related_id=referral.id,
    )
    return awarded > 0
