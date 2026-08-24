from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database import get_db
from app.deps import CurrentUser, get_current_user
from app.entitlements import entitlement_summary
from app.models import (
    User, UserEmail, UserProfile, UserPrivacy, UserStreak,
    PointsTransaction, University, Department, Subscription, Referral,
)
from app.schemas import StreakWithPointsOut
from app.services import points as points_service
from app.services.points import (
    REFERRER_REWARD, REFEREE_REWARD, REFERRAL_INVITER_REASONS,
)
from app.services.storage import get_storage

settings = get_settings()
router = APIRouter(prefix="/user", tags=["user"])

logger = logging.getLogger(__name__)

ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"}
MAX_AVATAR_MB = 5

REFERRAL_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class UserProfileOut(BaseModel):
    id: str
    full_name: str
    matric_number: str | None = None
    entry_year: int | None = None
    current_level: str | None = None
    school_email: str | None = None
    status: str = "STUDENT"
    college_id: str | None = None
    department_id: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    contribution_score: int = 0
    email_prompt_dismissed_at: str | None = None
    school_email_prompt_dismissed_at: str | None = None
    created_at: str | None = None
    college_name: str | None = None
    department_name: str | None = None
    department_code: str | None = None
    program_type: str | None = None

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    matric_number: str | None = None
    entry_year: int | None = None
    college_id: str | None = None
    department_id: str | None = None
    current_level: str | None = None


class EmailOut(BaseModel):
    id: str
    email: str
    is_primary: bool
    is_verified: bool

    model_config = {"from_attributes": True}


@router.get("/profile", response_model=UserProfileOut)
async def get_profile(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    u = user.user
    college_name = None
    department_name = None
    department_code = None
    program_type = None
    if u.university_id:
        university = await db.get(University, u.university_id)
        if university:
            college_name = university.name
            program_type = university.program_type
    if u.department_id:
        dept = await db.get(Department, u.department_id)
        if dept:
            department_name = dept.name
            department_code = dept.code

    return UserProfileOut(
        id=u.id, full_name=u.full_name, matric_number=u.matric_number,
        entry_year=u.entry_year, current_level=u.current_level,
        school_email=u.school_email, status=u.status.value,
        college_id=u.university_id, department_id=u.department_id,
        bio=u.bio, avatar_url=u.avatar_url, contribution_score=u.contribution_score,
        email_prompt_dismissed_at=str(u.email_prompt_dismissed_at) if u.email_prompt_dismissed_at else None,
        school_email_prompt_dismissed_at=str(u.school_email_prompt_dismissed_at) if u.school_email_prompt_dismissed_at else None,
        created_at=str(u.created_at) if u.created_at else None,
        college_name=college_name, department_name=department_name,
        department_code=department_code, program_type=program_type,
    )


@router.patch("/profile", response_model=UserProfileOut)
async def update_profile(
    payload: UpdateProfileRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    u = user.user
    if payload.full_name is not None:
        u.full_name = payload.full_name.strip()
    if payload.matric_number is not None:
        u.matric_number = payload.matric_number
    if payload.entry_year is not None:
        u.entry_year = payload.entry_year
    if payload.college_id is not None:
        u.university_id = payload.college_id
    if payload.department_id is not None:
        u.department_id = payload.department_id
    if payload.current_level is not None:
        u.current_level = payload.current_level
        u.level_updated_at = datetime.now(timezone.utc)

    await db.flush()
    return await get_profile(user=user, db=db)


def _guess_image_content_type(filename: str | None, content_type: str | None) -> str | None:
    if content_type in ALLOWED_AVATAR_TYPES:
        return content_type
    if not filename or "." not in filename:
        return content_type
    ext = filename.rsplit(".", 1)[-1].lower()
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, content_type)


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content_type = _guess_image_content_type(file.filename, file.content_type)
    if content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")

    data = await file.read()
    if len(data) > MAX_AVATAR_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")

    ext = file.filename.split(".")[-1] if file.filename else "jpg"
    path = f"avatars/{user.id}.{ext}"

    storage = get_storage()
    try:
        url = await storage.upload(settings.supabase_avatars_bucket, path, data, content_type)
    except Exception as exc:
        logger.warning("Avatar storage upload failed for %s: %s", user.id, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Could not save avatar to storage ({type(exc).__name__}: {exc}). Please try again.",
        ) from exc

    user.user.avatar_url = url
    await db.flush()
    return {"avatar_url": url}


@router.post("/link-backup-email")
async def link_backup_email(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.email:
        raise HTTPException(status_code=400, detail="No email in token")

    existing = await db.execute(
        select(UserEmail).where(UserEmail.email == user.email)
    )
    if existing.scalar_one_or_none():
        return {"message": "Email already linked"}

    ue = UserEmail(email=user.email, user_id=user.id, is_primary=False, is_verified=True)
    db.add(ue)
    user.user.contribution_score += 50
    db.add(PointsTransaction(user_id=user.id, amount=50, reason="backup_email_linked"))
    await db.flush()
    return {"message": "Email linked", "points_earned": 50}


@router.post("/dismiss-email-prompt")
async def dismiss_email_prompt(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.user.email_prompt_dismissed_at = datetime.now(timezone.utc)
    await db.flush()
    return {"message": "Dismissed"}


@router.post("/dismiss-school-email-prompt")
async def dismiss_school_email_prompt(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.user.school_email_prompt_dismissed_at = datetime.now(timezone.utc)
    await db.flush()
    return {"message": "Dismissed"}


@router.post("/school-email")
async def set_school_email(
    email: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not email.endswith(".edu.ng"):
        raise HTTPException(status_code=400, detail="Must be a .edu.ng email")
    user.user.school_email = email
    await db.flush()
    return {"message": "School email set"}


@router.post("/update-level")
async def update_level(
    level: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    valid = ["100L", "200L", "300L", "400L", "500L", "Spillover"]
    if level not in valid:
        raise HTTPException(status_code=400, detail=f"Level must be one of {valid}")
    user.user.current_level = level
    user.user.level_updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"message": "Level updated"}


@router.post("/graduate")
async def graduate(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.user.status = "ALUMNI"
    user.user.graduated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"message": "Graduated"}


@router.get("/backup-status")
async def backup_status(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dismissed = user.user.email_prompt_dismissed_at
    if dismissed and (datetime.now(timezone.utc) - dismissed.replace(tzinfo=timezone.utc)) < timedelta(days=14):
        return {"should_prompt": False}
    count = await db.execute(
        select(func.count()).select_from(UserEmail).where(UserEmail.user_id == user.id)
    )
    return {"should_prompt": count.scalar() < 2}


@router.get("/streak", response_model=StreakWithPointsOut)
async def get_streak(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserStreak).where(UserStreak.user_id == user.id))
    streak = result.scalar_one_or_none()
    pts = await db.execute(
        select(func.coalesce(func.sum(PointsTransaction.amount), 0))
        .where(PointsTransaction.user_id == user.id)
    )
    total = pts.scalar()
    return StreakWithPointsOut(
        current_streak=streak.current_streak if streak else 0,
        longest_streak=streak.longest_streak if streak else 0,
        last_activity_at=str(streak.last_activity_at) if streak else None,
        total_points=total or 0,
    )


@router.post("/check-in")
async def check_in(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserStreak).where(UserStreak.user_id == user.id))
    streak = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if not streak:
        streak = UserStreak(
            user_id=user.id, current_streak=1, longest_streak=1,
            last_activity_at=now, streak_started_at=now,
        )
        db.add(streak)
        user.user.user_streak_id = streak.id
    else:
        last = streak.last_activity_at.replace(tzinfo=timezone.utc) if streak.last_activity_at else None
        if last and (now - last).total_seconds() < 86400:
            return {"message": "Already checked in today", "streak": streak.current_streak}
        if last and (now - last).total_seconds() < 172800:
            streak.current_streak += 1
        else:
            streak.current_streak = 1
            streak.streak_started_at = now
        streak.longest_streak = max(streak.longest_streak, streak.current_streak)
        streak.last_activity_at = now

    base = 10
    bonus = (streak.current_streak // 5) * 5
    points = base + bonus
    user.user.contribution_score += points
    db.add(PointsTransaction(user_id=user.id, amount=points, reason="daily_login", description=f"Day {streak.current_streak} streak"))
    await db.flush()
    return {"message": "Checked in", "streak": streak.current_streak, "points_earned": points}


@router.get("/export-data")
async def export_data(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    u = user.user
    return {
        "full_name": u.full_name,
        "email": user.email,
        "matric_number": u.matric_number,
        "entry_year": u.entry_year,
        "current_level": u.current_level,
        "status": u.status.value,
        "college_id": u.university_id,
        "department_id": u.department_id,
        "bio": u.bio,
        "contribution_score": u.contribution_score,
        "created_at": str(u.created_at) if u.created_at else None,
    }


class AiTokensOut(BaseModel):
    used: int
    limit: int
    remaining: int
    is_premium: bool
    plan: str
    plan_name: str
    quota_remaining: int
    storage_total_bytes: int
    storage_used_bytes: int
    storage_remaining_bytes: int
    expires_at: str | None
    has_paid_pass: bool


@router.get("/ai-tokens", response_model=AiTokensOut)
async def get_ai_tokens(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    u = user.user

    summary = await entitlement_summary(db, u.id, u.created_at, daily_used=u.daily_tokens_used)

    return AiTokensOut(
        used=summary["quota_used"],
        limit=summary["quota_total"],
        remaining=summary["quota_remaining"],
        is_premium=summary["has_paid_pass"],
        plan=summary["plan"],
        plan_name=summary["plan_name"],
        quota_remaining=summary["quota_remaining"],
        storage_total_bytes=summary["storage_total_bytes"],
        storage_used_bytes=summary["storage_used_bytes"],
        storage_remaining_bytes=summary["storage_remaining_bytes"],
        expires_at=summary["expires_at"],
        has_paid_pass=summary["has_paid_pass"],
    )


class ReferralCodeOut(BaseModel):
    code: str
    url: str
    points_per_referral: int
    total_earned: int


class ReferralOut(BaseModel):
    referee_name: str | None = None
    referee_avatar: str | None = None
    created_at: str | None = None
    points_earned: int = REFERRER_REWARD


async def _ensure_referral_code(user: User, db: AsyncSession) -> str:
    if user.referral_code:
        return user.referral_code
    for _ in range(5):
        code = "V" + "".join(secrets.choice(REFERRAL_CODE_ALPHABET) for _ in range(7))
        existing = await db.execute(select(User.id).where(User.referral_code == code))
        if existing.scalar_one_or_none() is None:
            user.referral_code = code
            await db.flush()
            return code
    raise HTTPException(status_code=500, detail="Could not generate a unique referral code")


@router.get("/referral-code", response_model=ReferralCodeOut)
async def get_referral_code(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    code = await _ensure_referral_code(user.user, db)
    earned = await db.execute(
        select(func.coalesce(func.sum(PointsTransaction.amount), 0))
        .where(
            PointsTransaction.user_id == user.id,
            PointsTransaction.reason.in_(REFERRAL_INVITER_REASONS),
        )
    )
    return ReferralCodeOut(
        code=code,
        url=f"{settings.frontend_url or 'https://vylix-web.vercel.app'}/?ref={code}",
        points_per_referral=REFERRER_REWARD,
        total_earned=earned.scalar() or 0,
    )


@router.get("/referrals", response_model=list[ReferralOut])
async def list_referrals(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Referral, User.full_name, User.avatar_url)
        .join(User, User.id == Referral.referee_id)
        .where(Referral.referrer_id == user.id)
        .order_by(Referral.created_at.desc())
        .limit(50)
    )
    return [
        ReferralOut(
            referee_name=name,
            referee_avatar=avatar,
            created_at=str(r.created_at) if r.created_at else None,
            points_earned=REFERRER_REWARD,
        )
        for r, name, avatar in result.all()
    ]


class ReferralClaimRequest(BaseModel):
    code: str


class ReferralClaimOut(BaseModel):
    message: str
    points_earned: int


@router.post("/referrals/claim", response_model=ReferralClaimOut)
async def claim_referral(
    payload: ReferralClaimRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    code = payload.code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Referral code is required")

    if user.user.referral_code == code:
        raise HTTPException(status_code=400, detail="You can't use your own referral code")

    referrer = (await db.execute(select(User).where(User.referral_code == code))).scalar_one_or_none()
    if not referrer:
        raise HTTPException(status_code=400, detail="Invalid referral code")

    invite_count = await db.execute(
        select(func.count()).select_from(Referral).where(Referral.referrer_id == referrer.id)
    )
    if invite_count.scalar_one() >= settings.max_referees_per_referrer:
        raise HTTPException(
            status_code=400,
            detail="This invite code has reached its limit of "
                   f"{settings.max_referees_per_referrer} people",
        )

    already = await db.execute(
        select(Referral.id).where(Referral.referee_id == user.id)
    )
    if already.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="You've already used a referral code")

    db.add(Referral(referrer_id=referrer.id, referee_id=user.id))

    # The joiner gets their welcome points now; the inviter is paid once the
    # invitee spends a first AI query (see services.points.maybe_activate_referral)
    # so rewards track activated users, not raw signups.
    awarded = await points_service.award(
        db, user.id, REFEREE_REWARD,
        points_service.REASON_REFERRAL_WELCOME,
        description="You joined Vylix through a friend's invite",
    )
    await db.flush()
    return ReferralClaimOut(
        message="Referral applied",
        points_earned=awarded,
    )
