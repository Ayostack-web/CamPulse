from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from fastapi import HTTPException

from app.database import async_session
from app.deps import CurrentUser, check_ai_token_quota
from app.entitlements import (
    entitlement_summary,
    free_daily_limit,
    storage_allowance,
    storage_used,
)
from app.models import Course, Material, Subscription, Topic, User
from app import plans


async def _make_user(db, *, created_at=None) -> User:
    user = User(
        id=str(uuid.uuid4()),
        full_name="Entitlement Tester",
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    return user


async def _make_sub(db, user_id: str, plan: str, *, quota_used: int = 0) -> Subscription:
    cfg = plans.get_plan(plan)
    sub = Subscription(
        user_id=user_id,
        reference=f"TEST-{plan}-{uuid.uuid4()}",
        plan=plan,
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=cfg.duration_days or 1),
        quota_total=cfg.query_quota,
        quota_used=quota_used,
        storage_bytes_total=cfg.storage_bytes,
        storage_bytes_used=0,
    )
    db.add(sub)
    await db.flush()
    return sub


def _cu(user: User) -> CurrentUser:
    return CurrentUser(id=user.id, email="tester@example.com", full_name="Entitlement Tester", user=user)


@pytest.mark.asyncio
async def test_free_daily_limit_with_first_day_boost(db_schema):
    now = datetime.now(timezone.utc)
    assert free_daily_limit(now - timedelta(hours=1), now) == plans.FIRST_DAY_BOOST_LIMIT
    assert free_daily_limit(now - timedelta(days=2), now) == plans.FREE_DAILY_LIMIT


@pytest.mark.asyncio
async def test_free_quota_spends_and_stops_at_limit(db_schema):
    async with async_session() as db:
        user = await _make_user(db, created_at=datetime.now(timezone.utc) - timedelta(days=2))
        limit = plans.FREE_DAILY_LIMIT  # 5

        for _ in range(limit):
            await check_ai_token_quota(_cu(user), db)

        with pytest.raises(HTTPException) as exc:
            await check_ai_token_quota(_cu(user), db)
        assert exc.value.status_code == 429

        await db.refresh(user)
        assert user.daily_tokens_used == limit


@pytest.mark.asyncio
async def test_paid_quota_spends_atomically_and_hard_stops(db_schema):
    async with async_session() as db:
        user = await _make_user(db)
        sub = await _make_sub(db, user.id, "topup")
        sub.quota_total = 2
        await db.flush()

        await check_ai_token_quota(_cu(user), db)
        await check_ai_token_quota(_cu(user), db)

        with pytest.raises(HTTPException) as exc:
            await check_ai_token_quota(_cu(user), db)
        assert exc.value.status_code == 429

        await db.refresh(sub)
        assert sub.quota_used == 2


@pytest.mark.asyncio
async def test_topup_stacks_across_passes(db_schema):
    async with async_session() as db:
        user = await _make_user(db)
        sub_a = await _make_sub(db, user.id, "topup")
        sub_b = await _make_sub(db, user.id, "topup")
        sub_a.quota_total = 2
        sub_b.quota_total = 3
        await db.flush()

        for _ in range(5):
            await check_ai_token_quota(_cu(user), db)

        await db.refresh(sub_a)
        await db.refresh(sub_b)
        assert sub_a.quota_used + sub_b.quota_used == 5


@pytest.mark.asyncio
async def test_paid_pass_exhausted_no_free_fallback(db_schema):
    async with async_session() as db:
        user = await _make_user(db, created_at=datetime.now(timezone.utc) - timedelta(days=2))
        sub = await _make_sub(db, user.id, "night", quota_used=plans.get_plan("night").query_quota)

        with pytest.raises(HTTPException) as exc:
            await check_ai_token_quota(_cu(user), db)
        assert exc.value.status_code == 429
        # Free daily counter must NOT be consumed for a paid user.
        await db.refresh(user)
        assert user.daily_tokens_used == 0


@pytest.mark.asyncio
async def test_storage_allowance_and_usage(db_schema):
    async with async_session() as db:
        user = await _make_user(db)
        assert await storage_allowance(db, user.id) == plans.FREE_STORAGE_BYTES

        sub = await _make_sub(db, user.id, "semester")
        assert await storage_allowance(db, user.id) == plans.get_plan("semester").storage_bytes

        course = Course(
            id=str(uuid.uuid4()), code="ENT101", title="Entitlement Course",
            level=100, is_general=True,
        )
        db.add(course)
        await db.flush()

        topic = Topic(
            id=str(uuid.uuid4()),
            title="Entitlement Topic",
            course_id=course.id,
            author_id=user.id,
        )
        db.add(topic)
        await db.flush()

        material = Material(
            id=str(uuid.uuid4()),
            file_name="test.pdf",
            file_url="https://storage.test/materials/test.pdf",
            file_size=2 * 1024 * 1024,
            topic_id=topic.id,
            uploader_id=user.id,
        )
        db.add(material)
        await db.flush()

        assert await storage_used(db, user.id) == 2 * 1024 * 1024


@pytest.mark.asyncio
async def test_entitlement_summary_paid(db_schema):
    async with async_session() as db:
        user = await _make_user(db)
        sub = await _make_sub(db, user.id, "semester")
        sub.quota_used = 10
        await db.flush()

        summary = await entitlement_summary(db, user.id, user.created_at)
        assert summary["plan"] == "semester"
        assert summary["quota_total"] == plans.get_plan("semester").query_quota
        assert summary["quota_remaining"] == plans.get_plan("semester").query_quota - 10
        assert summary["has_paid_pass"] is True
        assert summary["daily_query_cap"] == plans.PAID_DAILY_SOFT_CAP


@pytest.mark.asyncio
async def test_entitlement_summary_free(db_schema):
    async with async_session() as db:
        user = await _make_user(db, created_at=datetime.now(timezone.utc) - timedelta(days=2))
        summary = await entitlement_summary(db, user.id, user.created_at, daily_used=2)
        assert summary["plan"] == "free"
        assert summary["quota_total"] == plans.FREE_DAILY_LIMIT
        assert summary["quota_remaining"] == plans.FREE_DAILY_LIMIT - 2
        assert summary["has_paid_pass"] is False
        assert summary["daily_query_cap"] is None
        assert summary["daily_queries_used"] is None
