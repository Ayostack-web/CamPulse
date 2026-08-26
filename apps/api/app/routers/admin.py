"""Admin dashboard API — stats, users, revenue, AI usage, paywall funnel.

All endpoints require admin role (checked via ``require_admin`` dependency).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, case, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import AdminUser, require_admin
from app.database import get_db
from app.models import (
    User, Subscription, AiUsage, Referral,
)
from app.core.postgres import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Response schemas ──────────────────────────────────────────────────


class AdminStatsOut(BaseModel):
    total_users: int
    users_today: int
    users_this_week: int
    active_subscriptions: int
    revenue_ngn_today: int
    revenue_ngn_week: int
    revenue_ngn_month: int
    ai_cost_usd_today: float
    ai_cost_usd_week: float
    ai_cost_usd_month: float
    ai_queries_today: int
    total_referrals: int


class AdminUserOut(BaseModel):
    id: str
    full_name: str
    email: str | None = None
    role: str = "student"
    status: str = "STUDENT"
    current_level: str | None = None
    matric_number: str | None = None
    created_at: str | None = None
    last_active_at: str | None = None
    subscription_plan: str | None = None
    subscription_expires: str | None = None
    ai_queries_today: int = 0
    contribution_score: int = 0

    model_config = {"from_attributes": True}


class AdminUsersOut(BaseModel):
    users: list[AdminUserOut]
    total: int
    page: int
    limit: int


class RevenueByPlanOut(BaseModel):
    plan: str
    count: int
    revenue_ngn: int


class AdminRevenueOut(BaseModel):
    total_revenue_ngn: int
    by_plan: list[RevenueByPlanOut]
    conversion_rate: float  # paid / total users


class AiUsageByFeatureOut(BaseModel):
    feature: str
    calls: int
    total_tokens: int
    est_cost_usd: float
    dedup_hits: int


class AiUsageByModelOut(BaseModel):
    model: str
    calls: int
    total_tokens: int
    est_cost_usd: float


class AdminAiUsageOut(BaseModel):
    total_cost_usd: float
    total_queries: int
    dedup_savings_usd: float
    by_feature: list[AiUsageByFeatureOut]
    by_model: list[AiUsageByModelOut]


# ── Helpers ───────────────────────────────────────────────────────────

_NOW = datetime.now(timezone.utc)


def _days_ago(n: int) -> datetime:
    return _NOW - timedelta(days=n)


# ── Endpoints ─────────────────────────────────────────────────────────


@router.get("/stats", response_model=AdminStatsOut)
async def admin_stats(
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    today_start = _NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    # Users
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    users_today = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= today_start)
    )).scalar() or 0
    users_this_week = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= week_start)
    )).scalar() or 0

    # Active subscriptions
    active_subs = (await db.execute(
        select(func.count(Subscription.id)).where(
            Subscription.status == "active",
            Subscription.expires_at > _NOW,
        )
    )).scalar() or 0

    # Revenue (from subscriptions — price_kobo from plans)
    from app import plans as plans_mod

    rev_today_q = await db.execute(
        select(func.coalesce(func.sum(
            case(
                (Subscription.plan == "night", plans_mod.PLANS["night"].price_kobo),
                (Subscription.plan == "weekly", plans_mod.PLANS["weekly"].price_kobo),
                (Subscription.plan == "semester", plans_mod.PLANS["semester"].price_kobo),
                (Subscription.plan == "session", plans_mod.PLANS["session"].price_kobo),
                (Subscription.plan == "topup", plans_mod.PLANS["topup"].price_kobo),
                (Subscription.plan == "topup_mini", plans_mod.PLANS["topup_mini"].price_kobo),
                (Subscription.plan == "micro", plans_mod.PLANS["micro"].price_kobo),
                else_=0,
            )
        ), 0)).where(Subscription.created_at >= today_start)
    )
    revenue_today = rev_today_q.scalar() or 0

    rev_week_q = await db.execute(
        select(func.coalesce(func.sum(
            case(
                (Subscription.plan == "night", plans_mod.PLANS["night"].price_kobo),
                (Subscription.plan == "weekly", plans_mod.PLANS["weekly"].price_kobo),
                (Subscription.plan == "semester", plans_mod.PLANS["semester"].price_kobo),
                (Subscription.plan == "session", plans_mod.PLANS["session"].price_kobo),
                (Subscription.plan == "topup", plans_mod.PLANS["topup"].price_kobo),
                (Subscription.plan == "topup_mini", plans_mod.PLANS["topup_mini"].price_kobo),
                (Subscription.plan == "micro", plans_mod.PLANS["micro"].price_kobo),
                else_=0,
            )
        ), 0)).where(Subscription.created_at >= week_start)
    )
    revenue_week = rev_week_q.scalar() or 0

    rev_month_q = await db.execute(
        select(func.coalesce(func.sum(
            case(
                (Subscription.plan == "night", plans_mod.PLANS["night"].price_kobo),
                (Subscription.plan == "weekly", plans_mod.PLANS["weekly"].price_kobo),
                (Subscription.plan == "semester", plans_mod.PLANS["semester"].price_kobo),
                (Subscription.plan == "session", plans_mod.PLANS["session"].price_kobo),
                (Subscription.plan == "topup", plans_mod.PLANS["topup"].price_kobo),
                (Subscription.plan == "topup_mini", plans_mod.PLANS["topup_mini"].price_kobo),
                (Subscription.plan == "micro", plans_mod.PLANS["micro"].price_kobo),
                else_=0,
            )
        ), 0)).where(Subscription.created_at >= month_start)
    )
    revenue_month = rev_month_q.scalar() or 0

    # AI costs
    ai_today = await db.execute(
        select(
            func.coalesce(func.sum(AiUsage.est_cost_usd), 0),
            func.coalesce(func.count(AiUsage.id), 0),
        ).where(AiUsage.created_at >= today_start)
    )
    ai_row = ai_today.one()
    ai_cost_today = float(ai_row[0] or 0)
    ai_queries_today = int(ai_row[1] or 0)

    ai_week = await db.execute(
        select(func.coalesce(func.sum(AiUsage.est_cost_usd), 0))
        .where(AiUsage.created_at >= week_start)
    )
    ai_cost_week = float(ai_week.scalar() or 0)

    ai_month = await db.execute(
        select(func.coalesce(func.sum(AiUsage.est_cost_usd), 0))
        .where(AiUsage.created_at >= month_start)
    )
    ai_cost_month = float(ai_month.scalar() or 0)

    # Referrals
    total_referrals = (await db.execute(select(func.count(Referral.id)))).scalar() or 0

    return AdminStatsOut(
        total_users=total_users,
        users_today=users_today,
        users_this_week=users_this_week,
        active_subscriptions=active_subs,
        revenue_ngn_today=revenue_today // 100,  # kobo → naira
        revenue_ngn_week=revenue_week // 100,
        revenue_ngn_month=revenue_month // 100,
        ai_cost_usd_today=round(ai_cost_today, 4),
        ai_cost_usd_week=round(ai_cost_week, 4),
        ai_cost_usd_month=round(ai_cost_month, 4),
        ai_queries_today=ai_queries_today,
        total_referrals=total_referrals,
    )


@router.get("/users", response_model=AdminUsersOut)
async def admin_users(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: str = Query(default=""),
    plan_filter: str = Query(default="", alias="plan"),
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(User)
    count_q = select(func.count(User.id))

    if search:
        like = f"%{search}%"
        where = or_(
            User.full_name.ilike(like),
            User.matric_number.ilike(like),
            User.school_email.ilike(like),
        )
        q = q.where(where)
        count_q = count_q.where(where)

    total = (await db.execute(count_q)).scalar() or 0

    q = q.order_by(User.created_at.desc())
    q = q.offset((page - 1) * limit).limit(limit)

    result = await db.execute(q)
    users = result.scalars().all()

    # Batch-fetch latest subscription for each user
    user_ids = [u.id for u in users]
    sub_map: dict[str, Subscription] = {}
    if user_ids:
        subs = await db.execute(
            select(Subscription)
            .where(Subscription.user_id.in_(user_ids))
            .where(Subscription.status == "active")
            .order_by(Subscription.created_at.desc())
        )
        for sub in subs.scalars().all():
            if sub.user_id not in sub_map:
                sub_map[sub.user_id] = sub

    # Batch-fetch today's AI query count per user
    today_start = _NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    ai_today_map: dict[str, int] = {}
    if user_ids:
        ai_rows = await db.execute(
            select(AiUsage.user_id, func.count(AiUsage.id))
            .where(AiUsage.user_id.in_(user_ids))
            .where(AiUsage.created_at >= today_start)
            .group_by(AiUsage.user_id)
        )
        for row in ai_rows.all():
            ai_today_map[row[0]] = row[1]

    # If plan filter is set, skip users without that plan
    out_users = []
    for u in users:
        sub = sub_map.get(u.id)
        plan_key = sub.plan if sub else None

        if plan_filter and plan_key != plan_filter:
            continue

        out_users.append(AdminUserOut(
            id=u.id,
            full_name=u.full_name,
            email=None,  # not exposed in list view for privacy
            role=u.role or "student",
            status=u.status.value if hasattr(u.status, 'value') else str(u.status),
            current_level=u.current_level,
            matric_number=u.matric_number,
            created_at=str(u.created_at) if u.created_at else None,
            last_active_at=str(u.last_active_at) if u.last_active_at else None,
            subscription_plan=plan_key,
            subscription_expires=str(sub.expires_at) if sub and sub.expires_at else None,
            ai_queries_today=ai_today_map.get(u.id, 0),
            contribution_score=u.contribution_score,
        ))

    return AdminUsersOut(
        users=out_users,
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/revenue", response_model=AdminRevenueOut)
async def admin_revenue(
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app import plans as plans_mod

    price_map = {
        p.key: p.price_kobo for p in plans_mod.PLANS.values()
    }

    # Revenue breakdown by plan
    rows = await db.execute(
        select(Subscription.plan, func.count(Subscription.id))
        .where(Subscription.status == "active")
        .group_by(Subscription.plan)
    )

    by_plan = []
    total_rev = 0
    for plan_key, count in rows.all():
        rev = count * price_map.get(plan_key, 0)
        total_rev += rev
        by_plan.append(RevenueByPlanOut(
            plan=plan_key,
            count=count,
            revenue_ngn=rev // 100,
        ))

    # Conversion rate
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    paid_users = (await db.execute(
        select(func.count(func.distinct(Subscription.user_id)))
        .where(Subscription.status == "active")
    )).scalar() or 0
    conversion = (paid_users / total_users * 100) if total_users > 0 else 0.0

    return AdminRevenueOut(
        total_revenue_ngn=total_rev // 100,
        by_plan=sorted(by_plan, key=lambda x: x.revenue_ngn, reverse=True),
        conversion_rate=round(conversion, 1),
    )


@router.get("/ai-usage", response_model=AdminAiUsageOut)
async def admin_ai_usage(
    days: int = Query(default=30, ge=1, le=365),
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    since = _NOW - timedelta(days=days)

    # Totals
    totals = await db.execute(
        select(
            func.coalesce(func.sum(AiUsage.est_cost_usd), 0),
            func.coalesce(func.count(AiUsage.id), 0),
            func.coalesce(func.sum(
                case((AiUsage.dedup_hit.is_(True), AiUsage.est_cost_usd), else_=0)
            ), 0),
        ).where(AiUsage.created_at >= since)
    )
    row = totals.one()
    total_cost = float(row[0] or 0)
    total_queries = int(row[1] or 0)
    dedup_savings = float(row[2] or 0)

    # By feature
    feat_rows = await db.execute(
        select(
            AiUsage.feature,
            func.count(AiUsage.id),
            func.coalesce(func.sum(AiUsage.total_tokens), 0),
            func.coalesce(func.sum(AiUsage.est_cost_usd), 0),
            func.coalesce(func.sum(
                case((AiUsage.dedup_hit.is_(True), 1), else_=0)
            ), 0),
        )
        .where(AiUsage.created_at >= since)
        .group_by(AiUsage.feature)
        .order_by(func.sum(AiUsage.est_cost_usd).desc())
    )
    by_feature = [
        AiUsageByFeatureOut(
            feature=r[0],
            calls=r[1],
            total_tokens=int(r[2]),
            est_cost_usd=round(float(r[3]), 4),
            dedup_hits=int(r[4]),
        )
        for r in feat_rows.all()
    ]

    # By model
    model_rows = await db.execute(
        select(
            AiUsage.model,
            func.count(AiUsage.id),
            func.coalesce(func.sum(AiUsage.total_tokens), 0),
            func.coalesce(func.sum(AiUsage.est_cost_usd), 0),
        )
        .where(AiUsage.created_at >= since)
        .group_by(AiUsage.model)
        .order_by(func.sum(AiUsage.est_cost_usd).desc())
    )
    by_model = [
        AiUsageByModelOut(
            model=r[0],
            calls=r[1],
            total_tokens=int(r[2]),
            est_cost_usd=round(float(r[3]), 4),
        )
        for r in model_rows.all()
    ]

    return AdminAiUsageOut(
        total_cost_usd=round(total_cost, 4),
        total_queries=total_queries,
        dedup_savings_usd=round(dedup_savings, 4),
        by_feature=by_feature,
        by_model=by_model,
    )


# ── Paywall funnel analytics ──────────────────────────────────────


class PaywallFunnelOut(BaseModel):
    event_type: str
    count: int


class PaywallFunnelResponse(BaseModel):
    total_shown: int
    total_dismissed: int
    total_plan_clicked: int
    total_checkout_started: int
    total_checkout_completed: int
    total_checkout_failed: int
    conversion_rate: float  # completed / started
    by_plan: list[dict]
    recent_events: list[dict]


@router.get("/paywall-funnel", response_model=PaywallFunnelResponse)
async def admin_paywall_funnel(
    days: int = Query(default=30, ge=1, le=365),
    admin: AdminUser = Depends(require_admin),
):
    """Paywall conversion funnel — how many users see → click → pay."""
    with get_connection() as conn:
        # Counts by event type
        rows = conn.exec_driver_sql(
            "SELECT event_type, COUNT(*)::int FROM paywall_events "
            "WHERE created_at >= NOW() - INTERVAL '%s days' "
            "GROUP BY event_type" % days
        ).fetchall()
        counts = {r[0]: r[1] for r in rows}

        shown = counts.get("paywall_shown", 0)
        dismissed = counts.get("paywall_dismissed", 0)
        clicked = counts.get("plan_clicked", 0)
        started = counts.get("checkout_started", 0)
        completed = counts.get("checkout_completed", 0)
        failed = counts.get("checkout_failed", 0)

        # Breakdown by plan
        plan_rows = conn.exec_driver_sql(
            "SELECT plan_key, event_type, COUNT(*)::int FROM paywall_events "
            "WHERE created_at >= NOW() - INTERVAL '%s days' "
            "AND plan_key IS NOT NULL "
            "GROUP BY plan_key, event_type " % days
        ).fetchall()

        plan_map: dict[str, dict] = {}
        for plan_key, event_type, cnt in plan_rows:
            if plan_key not in plan_map:
                plan_map[plan_key] = {"plan": plan_key}
            plan_map[plan_key][event_type] = cnt
        by_plan = sorted(plan_map.values(), key=lambda x: x.get("checkout_completed", 0), reverse=True)

        # Last 20 events
        recent_rows = conn.exec_driver_sql(
            "SELECT event_type, plan_key, created_at::text FROM paywall_events "
            "ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        recent = [
            {"event_type": r[0], "plan_key": r[1], "created_at": r[2]}
            for r in recent_rows
        ]

    conversion = (completed / started * 100) if started > 0 else 0.0

    return PaywallFunnelResponse(
        total_shown=shown,
        total_dismissed=dismissed,
        total_plan_clicked=clicked,
        total_checkout_started=started,
        total_checkout_completed=completed,
        total_checkout_failed=failed,
        conversion_rate=round(conversion, 1),
        by_plan=by_plan,
        recent_events=recent,
    )
