from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import CurrentUser, get_current_user
from app.models import (
    Material, Topic, Course, Notification, UserStreak,
    PointsTransaction, TopicQuestion, QuestionAnswer,
)

router = APIRouter(prefix="/digest", tags=["digest"])


class CourseActivity(BaseModel):
    course_id: str
    course_code: str
    course_title: str
    new_materials: int
    new_questions: int
    active_classmates: int


class DailyDigest(BaseModel):
    greeting: str
    streak: int
    total_points: int
    new_notifications: int
    courses_with_activity: list[CourseActivity]
    recent_questions: list[dict]
    study_tip: str


STUDY_TIPS = [
    "Active recall is more effective than re-reading. Try closing your notes and writing what you remember.",
    "The Pomodoro technique works: 25 minutes focused study, 5 minute break, repeat.",
    "Teaching a concept to someone else is the best way to solidify your understanding.",
    "Spaced repetition beats cramming. Review material 1 day, 3 days, and 7 days after learning it.",
    "Start with the hardest topic when your energy is highest. Save easier review for later.",
    "Practice past questions under timed conditions to simulate exam pressure.",
    "Join a study group — explaining concepts to peers reinforces your own learning.",
    "Take handwritten notes instead of typing. Studies show better retention with pen and paper.",
    "Sleep is essential for memory consolidation. An all-nighter hurts more than it helps.",
    "Break large topics into small chunks. Master one chunk before moving to the next.",
]


@router.get("/daily", response_model=DailyDigest)
async def daily_digest(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    hour = now.hour

    if hour < 12:
        greeting = f"Good morning, {user.full_name.split()[0]}"
    elif hour < 17:
        greeting = f"Good afternoon, {user.full_name.split()[0]}"
    else:
        greeting = f"Good evening, {user.full_name.split()[0]}"

    streak_result = await db.execute(
        select(UserStreak).where(UserStreak.user_id == user.id)
    )
    streak = streak_result.scalar_one_or_none()

    points_result = await db.execute(
        select(func.coalesce(func.sum(PointsTransaction.amount), 0))
        .where(PointsTransaction.user_id == user.id)
    )
    total_points = points_result.scalar() or 0

    notif_result = await db.execute(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at == None)
    )
    new_notifications = notif_result.scalar() or 0

    two_days_ago = now - timedelta(days=2)

    recent_questions_q = await db.execute(
        select(TopicQuestion, Course.code, Course.title)
        .join(Topic, Topic.id == TopicQuestion.topic_id)
        .join(Course, Course.id == Topic.course_id)
        .where(TopicQuestion.created_at >= two_days_ago)
        .order_by(TopicQuestion.created_at.desc())
        .limit(5)
    )
    recent_questions = [
        {
            "id": q.id,
            "title": q.title,
            "course_code": cc,
            "course_title": ct,
            "created_at": str(q.created_at) if q.created_at else None,
        }
        for q, cc, ct in recent_questions_q.all()
    ]

    user_courses_q = await db.execute(
        select(Course.id, Course.code, Course.title)
        .join(Topic, Topic.course_id == Course.id)
        .join(Material, Material.topic_id == Topic.id)
        .where(Material.uploader_id == user.id)
        .group_by(Course.id, Course.code, Course.title)
    )
    user_course_ids = {cid: (cc, ct) for cid, cc, ct in user_courses_q.all()}

    # Grouped aggregates per course — constant query count regardless of how
    # many courses the user has (the previous loop ran 3 queries per course).
    course_ids = list(user_course_ids.keys())
    new_materials_by_course: dict[str, int] = {}
    new_questions_by_course: dict[str, int] = {}
    classmates_by_course: dict[str, int] = {}

    if course_ids:
        new_mat_q = await db.execute(
            select(Topic.course_id, func.count(Material.id))
            .join(Material, Material.topic_id == Topic.id)
            .where(Topic.course_id.in_(course_ids))
            .where(Material.uploaded_at >= two_days_ago)
            .group_by(Topic.course_id)
        )
        new_materials_by_course = {cid: cnt for cid, cnt in new_mat_q.all()}

        new_qs_q = await db.execute(
            select(Topic.course_id, func.count(TopicQuestion.id))
            .join(TopicQuestion, TopicQuestion.topic_id == Topic.id)
            .where(Topic.course_id.in_(course_ids))
            .where(TopicQuestion.created_at >= two_days_ago)
            .group_by(Topic.course_id)
        )
        new_questions_by_course = {cid: cnt for cid, cnt in new_qs_q.all()}

        classmates_q = await db.execute(
            select(Topic.course_id, func.count(func.distinct(Material.uploader_id)))
            .join(Material, Material.topic_id == Topic.id)
            .where(Topic.course_id.in_(course_ids))
            .where(Material.uploaded_at >= two_days_ago)
            .where(Material.uploader_id != user.id)
            .group_by(Topic.course_id)
        )
        classmates_by_course = {cid: cnt for cid, cnt in classmates_q.all()}

    courses_with_activity = []
    for cid, (cc, ct) in user_course_ids.items():
        new_mat = new_materials_by_course.get(cid, 0)
        new_qs = new_questions_by_course.get(cid, 0)
        active_classmates = classmates_by_course.get(cid, 0)

        if new_mat > 0 or new_qs > 0:
            courses_with_activity.append(CourseActivity(
                course_id=cid,
                course_code=cc,
                course_title=ct,
                new_materials=new_mat,
                new_questions=new_qs,
                active_classmates=active_classmates,
            ))

    courses_with_activity.sort(key=lambda c: c.new_materials + c.new_questions, reverse=True)

    tip_index = now.day % len(STUDY_TIPS)

    return DailyDigest(
        greeting=greeting,
        streak=streak.current_streak if streak else 0,
        total_points=total_points,
        new_notifications=new_notifications,
        courses_with_activity=courses_with_activity[:5],
        recent_questions=recent_questions,
        study_tip=STUDY_TIPS[tip_index],
    )


class SocialPresence(BaseModel):
    active_now: int
    active_today: int
    classmates_active: list[dict]


@router.get("/social-presence", response_model=SocialPresence)
async def social_presence(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    five_min_ago = now - timedelta(minutes=5)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    active_now_result = await db.execute(
        select(func.count()).select_from(User)
        .where(User.last_active_at > five_min_ago)
    )
    active_now = active_now_result.scalar() or 0

    active_today_result = await db.execute(
        select(func.count()).select_from(User)
        .where(User.last_active_at > today_start)
    )
    active_today = active_today_result.scalar() or 0

    classmates_active = []
    if user.user.department_id and user.user.current_level:
        classmates_result = await db.execute(
            select(User.id, User.full_name, User.avatar_url, User.last_active_at)
            .where(
                User.department_id == user.user.department_id,
                User.current_level == user.user.current_level,
                User.id != user.id,
                User.last_active_at > five_min_ago,
            )
            .limit(10)
        )
        classmates_active = [
            {
                "user_id": uid,
                "full_name": fn,
                "avatar_url": av,
                "last_active_at": str(la) if la else None,
            }
            for uid, fn, av, la in classmates_result.all()
        ]

    return SocialPresence(
        active_now=active_now,
        active_today=active_today,
        classmates_active=classmates_active,
    )
