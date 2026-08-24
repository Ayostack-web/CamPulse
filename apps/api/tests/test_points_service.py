from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.database import async_session
from app.models import PointsTransaction, Referral, Subscription, User
from app.services import points


async def _make_user(db) -> User:
    user = User(id=str(uuid.uuid4()), full_name="Points Tester")
    db.add(user)
    await db.flush()
    return user


def _settings_override(**overrides):
    settings = get_settings()
    original = {key: getattr(settings, key) for key in overrides}
    for key, value in overrides.items():
        setattr(settings, key, value)
    return original


@pytest.mark.asyncio
async def test_award_credits_and_mirrors_contribution_score(db_schema):
    async with async_session() as db:
        user = await _make_user(db)
        awarded = await points.award(
            db, user.id, 25, points.REASON_PQ_UPLOAD, related_id="m1"
        )
        await db.commit()

        assert awarded == 25
        await db.refresh(user)
        assert user.contribution_score == 25
        balance = await points.spendable_balance(db, user.id)
        assert balance == 25


@pytest.mark.asyncio
async def test_award_respects_weekly_earn_cap(db_schema):
    original = _settings_override(points_weekly_earn_cap=40)
    try:
        async with async_session() as db:
            user = await _make_user(db)
            first = await points.award(db, user.id, 30, points.REASON_PQ_UPLOAD)
            second = await points.award(db, user.id, 30, points.REASON_REFERRAL_WELCOME)
            await db.commit()

            assert first == 30
            assert second == 10
    finally:
        for key, value in original.items():
            setattr(get_settings(), key, value)


@pytest.mark.asyncio
async def test_spendable_balance_expires_old_points(db_schema):
    async with async_session() as db:
        user = await _make_user(db)
        stale_cutoff = datetime.now(timezone.utc) - timedelta(
            days=get_settings().points_expiry_days + 1
        )
        db.add(PointsTransaction(
            user_id=user.id, amount=100,
            reason=points.REASON_PQ_UPLOAD, created_at=stale_cutoff,
        ))
        db.add(PointsTransaction(
            user_id=user.id, amount=20, reason=points.REASON_CHECK_IN,
        ))
        await db.commit()

        lifetime = await db.execute(
            select(PointsTransaction.amount).where(PointsTransaction.user_id == user.id)
        )
        assert sum(lifetime.scalars().all()) == 120
        spendable = await points.spendable_balance(db, user.id)
        assert spendable == 20


@pytest.mark.asyncio
async def test_redeem_reward_mints_pass_and_ledgers_spend(db_schema):
    async with async_session() as db:
        user = await _make_user(db)
        await points.award(db, user.id, 100, points.REASON_PQ_MILESTONE)

        result = await points.redeem_reward(db, user.id, "ai_queries_25")
        await db.commit()

        assert result["points_spent"] == 100
        assert result["queries_granted"] == 25
        assert result["balance_after"] == 0

        sub = (
            await db.execute(
                select(Subscription).where(
                    Subscription.reference == f"REWARD-{result['purchase_id']}"
                )
            )
        ).scalar_one()
        assert sub.quota_total == 25
        assert sub.quota_used == 0
        assert sub.status == "active"

        spend = (
            await db.execute(
                select(PointsTransaction).where(
                    PointsTransaction.user_id == user.id,
                    PointsTransaction.reason == points.REASON_REDEMPTION,
                )
            )
        ).scalar_one()
        assert spend.amount == -100


@pytest.mark.asyncio
async def test_redeem_reward_rejects_insufficient_balance(db_schema):
    async with async_session() as db:
        user = await _make_user(db)
        await points.award(db, user.id, 50, points.REASON_CHECK_IN)

        with pytest.raises(ValueError, match="insufficient_points"):
            await points.redeem_reward(db, user.id, "ai_queries_25")


@pytest.mark.asyncio
async def test_referral_activation_pays_referrer_once(db_schema):
    async with async_session() as db:
        referrer = await _make_user(db)
        referee = await _make_user(db)
        referral = Referral(referrer_id=referrer.id, referee_id=referee.id)
        db.add(referral)
        await db.flush()

        paid_first = await points.maybe_activate_referral(db, referee.id)
        await db.commit()
        assert paid_first is True

        await db.refresh(referrer)
        assert referrer.contribution_score == points.REFERRER_REWARD

        paid_again = await points.maybe_activate_referral(db, referee.id)
        await db.commit()
        assert paid_again is False

        await db.refresh(referrer)
        assert referrer.contribution_score == points.REFERRER_REWARD


@pytest.mark.asyncio
async def test_referral_activation_noop_without_referral(db_schema):
    async with async_session() as db:
        user = await _make_user(db)
        paid = await points.maybe_activate_referral(db, user.id)
        assert paid is False
