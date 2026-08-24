from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import CurrentUser, get_current_user
from app.models import (
    UserStreak, PointsTransaction, User, Badge, UserBadge,
)
from app.schemas import StreakOut, PointsOut, TransactionOut, LeaderboardEntry
from app.services import points as points_service

router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.post("/check-in")
async def check_in(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserStreak).where(UserStreak.user_id == user.id))
    streak = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if not streak:
        streak = UserStreak(user_id=user.id, current_streak=1, longest_streak=1, last_activity_at=now, streak_started_at=now)
        db.add(streak)
    else:
        last = streak.last_activity_at.replace(tzinfo=timezone.utc) if streak.last_activity_at else None
        if last and (now - last).total_seconds() < 86400:
            return {"message": "Already checked in", "streak": streak.current_streak}
        if last and (now - last).total_seconds() < 172800:
            streak.current_streak += 1
        else:
            streak.current_streak = 1
            streak.streak_started_at = now
        streak.longest_streak = max(streak.longest_streak, streak.current_streak)
        streak.last_activity_at = now

    points = 10 + (streak.current_streak // 5) * 5
    awarded = await points_service.award(
        db, user.id, points, points_service.REASON_CHECK_IN,
        description="Daily check-in",
    )
    await db.flush()
    return {"streak": streak.current_streak, "points_earned": awarded}


@router.get("/streak", response_model=StreakOut)
async def get_streak(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserStreak).where(UserStreak.user_id == user.id))
    s = result.scalar_one_or_none()
    return StreakOut(
        current_streak=s.current_streak if s else 0,
        longest_streak=s.longest_streak if s else 0,
        last_activity_at=str(s.last_activity_at) if s else None,
    )


@router.get("/points", response_model=PointsOut)
async def get_points(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.coalesce(func.sum(PointsTransaction.amount), 0))
        .where(PointsTransaction.user_id == user.id)
    )
    total = int(result.scalar() or 0)
    spendable = await points_service.spendable_balance(db, user.id)
    return PointsOut(total_points=total, spendable_points=spendable)


@router.get("/points/history", response_model=list[TransactionOut])
async def points_history(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PointsTransaction)
        .where(PointsTransaction.user_id == user.id)
        .order_by(PointsTransaction.created_at.desc())
        .limit(50)
    )
    return [
        TransactionOut(
            id=t.id, amount=t.amount, reason=t.reason,
            description=t.description, created_at=str(t.created_at) if t.created_at else None,
        )
        for t in result.scalars().all()
    ]


@router.get("/leaderboard/streaks", response_model=list[LeaderboardEntry])
async def streak_leaderboard(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserStreak, User.full_name, User.avatar_url)
        .join(User, User.id == UserStreak.user_id)
        .order_by(UserStreak.current_streak.desc())
        .limit(10)
    )
    return [
        LeaderboardEntry(user_id=s.user_id, full_name=fn, avatar_url=av, value=s.current_streak)
        for s, fn, av in result.all()
    ]


@router.get("/leaderboard/points", response_model=list[LeaderboardEntry])
async def points_leaderboard(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User.id, User.full_name, User.avatar_url, User.contribution_score)
        .order_by(User.contribution_score.desc())
        .limit(10)
    )
    return [
        LeaderboardEntry(user_id=uid, full_name=fn, avatar_url=av, value=cs)
        for uid, fn, av, cs in result.all()
    ]


class BadgeOut(BaseModel):
    id: str
    code: str
    name: str
    description: str
    icon: str
    rarity: str
    earned_at: str | None = None

    model_config = {"from_attributes": True}


@router.get("/badges", response_model=list[BadgeOut])
async def get_user_badges(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Badge, UserBadge.earned_at)
        .join(UserBadge, UserBadge.badge_id == Badge.id)
        .where(UserBadge.user_id == user.id)
        .order_by(UserBadge.earned_at.desc())
    )
    return [
        BadgeOut(
            id=b.id, code=b.code, name=b.name, description=b.description,
            icon=b.icon, rarity=b.rarity.value,
            earned_at=str(earned) if earned else None,
        )
        for b, earned in result.all()
    ]


@router.get("/streak-and-points")
async def get_streak_and_points(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    streak_result = await db.execute(
        select(UserStreak).where(UserStreak.user_id == user.id)
    )
    streak = streak_result.scalar_one_or_none()

    points_result = await db.execute(
        select(func.coalesce(func.sum(PointsTransaction.amount), 0))
        .where(PointsTransaction.user_id == user.id)
    )
    total_points = points_result.scalar() or 0

    return {
        "current_streak": streak.current_streak if streak else 0,
        "longest_streak": streak.longest_streak if streak else 0,
        "total_points": total_points,
        "spendable_points": await points_service.spendable_balance(db, user.id),
        "last_activity_at": str(streak.last_activity_at) if streak and streak.last_activity_at else None,
    }


class RewardItemOut(BaseModel):
    code: str
    name: str
    description: str
    category: str
    points_cost: int
    affordable: bool


class RewardsOut(BaseModel):
    balance: int
    items: list[RewardItemOut]


@router.get("/rewards", response_model=RewardsOut)
async def list_rewards(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await points_service.ensure_reward_items(db)
    await db.commit()
    balance = await points_service.spendable_balance(db, user.id)
    return RewardsOut(
        balance=balance,
        items=[
            RewardItemOut(
                code=i.code, name=i.name, description=i.description,
                category=i.category, points_cost=i.points_cost,
                affordable=balance >= i.points_cost,
            )
            for i in items
        ],
    )


class RedeemRequest(BaseModel):
    reward_code: str


class RedeemOut(BaseModel):
    message: str
    reward_code: str
    name: str
    points_spent: int
    queries_granted: int
    expires_at: str
    balance_after: int


@router.post("/rewards/redeem", response_model=RedeemOut)
async def redeem_reward(
    payload: RedeemRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await points_service.redeem_reward(db, user.id, payload.reward_code.strip())
    except ValueError as exc:
        detail = {
            "unknown_reward": "Unknown reward",
            "insufficient_points": "Not enough points for this reward",
        }.get(str(exc), "Could not redeem reward")
        raise HTTPException(status_code=400, detail=detail)

    await db.commit()
    return RedeemOut(
        message=f"{result['name']} activated on your account",
        reward_code=result["reward_code"],
        name=result["name"],
        points_spent=result["points_spent"],
        queries_granted=result["queries_granted"],
        expires_at=str(result["expires_at"]),
        balance_after=result["balance_after"],
    )
