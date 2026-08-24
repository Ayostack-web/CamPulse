"""Tests for the ai_usage cost-attribution table.

These run wherever the other db_schema tests run (CI has real Postgres).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.database import async_session
from app.models import AiUsage, User
from app.services.usage_log import _plan_cache, record_ai_usage


@pytest.mark.asyncio
async def test_record_ai_usage_anonymous_is_system_plan(db_schema):
    _plan_cache.clear()
    record_ai_usage(
        model="gemini-flash-lite-latest",
        feature="general_chat",
        user_id=None,
        prompt_tokens=100,
        completion_tokens=50,
        est_cost_usd=0.000045,
    )

    async with async_session() as db:
        result = await db.execute(
            select(AiUsage).where(AiUsage.feature == "general_chat")
        )
        row = result.scalars().first()
        await db.rollback()

    assert row is not None
    assert row.user_id is None
    assert row.user_plan == "system"
    assert row.prompt_tokens == 100
    assert row.completion_tokens == 50
    assert row.total_tokens == 150
    assert row.dedup_hit is False
    assert abs(row.est_cost_usd - 0.000045) < 1e-9


@pytest.mark.asyncio
async def test_record_ai_usage_unknown_user_defaults_free(db_schema):
    _plan_cache.clear()
    fake_user = str(uuid.uuid4())  # no subscriptions rows → free tier
    record_ai_usage(
        model="gemini-pro-latest",
        feature="study_agent",
        user_id=fake_user,
        task_tier="complex",
        prompt_tokens=1000,
        completion_tokens=2000,
        est_cost_usd=0.026,
    )

    async with async_session() as db:
        result = await db.execute(
            select(AiUsage).where(AiUsage.user_id == fake_user)
        )
        row = result.scalars().first()
        await db.rollback()

    assert row is not None
    assert row.user_plan == "free"
    assert row.model == "gemini-pro-latest"
    assert row.task_tier == "complex"
    assert row.total_tokens == 3000


@pytest.mark.asyncio
async def test_record_ai_usage_paid_pass_snapshot(db_schema):
    from datetime import datetime, timedelta, timezone

    from app.models import Subscription

    _plan_cache.clear()
    user_id = str(uuid.uuid4())
    async with async_session() as db:
        db.add(
            User(
                id=user_id,
                full_name="Usage Tester",
                created_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            Subscription(
                user_id=user_id,
                reference=f"TEST-USAGE-{uuid.uuid4()}",
                plan="semester",
                status="active",
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                quota_total=2000,
                quota_used=5,
                storage_bytes_total=0,
                storage_bytes_used=0,
            )
        )
        await db.commit()

    record_ai_usage(
        model="gemini-flash-lite-latest",
        feature="study_agent",
        user_id=user_id,
        task_tier="standard",
        prompt_tokens=10,
        completion_tokens=20,
        dedup_hit=True,
    )

    async with async_session() as db:
        result = await db.execute(select(AiUsage).where(AiUsage.user_id == user_id))
        row = result.scalars().first()
        await db.rollback()

    assert row is not None
    assert row.user_plan == "semester"
    assert row.dedup_hit is True


@pytest.mark.asyncio
async def test_record_ai_usage_never_raises(db_schema, monkeypatch):
    """A broken DB connection must not propagate into the AI request path."""
    import app.core.postgres as pg

    def _broken_ctx():
        raise RuntimeError("db down")

    monkeypatch.setattr(pg, "get_connection", _broken_ctx)

    record_ai_usage(
        model="gemini-flash-lite-latest",
        feature="document_chat",
        user_id=str(uuid.uuid4()),
        prompt_tokens=1,
        completion_tokens=1,
    )
