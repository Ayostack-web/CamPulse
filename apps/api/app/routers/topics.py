from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import CurrentUser, get_current_user
from app.models import Topic, Course, User

router = APIRouter(prefix="/topics", tags=["topics"])


class TopicOut(BaseModel):
    id: str
    title: str
    course_id: str
    author_id: str
    is_active: bool
    last_activity: str | None = None

    model_config = {"from_attributes": True}


@router.get("/course/{course_id}", response_model=list[TopicOut])
async def list_topics_for_course(
    course_id: str,
    limit: int = Query(default=100, ge=1, le=300),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Department guard: verify course belongs to user's department or is general
    if not course.is_general and course.department_id != user.user.department_id:
        raise HTTPException(status_code=403, detail="Course not in your department")

    result = await db.execute(
        select(Topic)
        .where(Topic.course_id == course_id, Topic.is_active == True)
        .order_by(Topic.last_activity.desc())
        .limit(limit)
    )
    return result.scalars().all()
