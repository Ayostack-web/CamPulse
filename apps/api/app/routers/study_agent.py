from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import check_ai_token_quota, CurrentUser, get_current_user
from app.entitlements import has_active_paid_pass
from app.services.academic_agent import run_vylix_academic_agent
from app.services.course_scope import course_exists_anywhere, find_course
from app.services.gemini import GeminiError, error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/study-agent", tags=["study-agent"])


async def _resolve_scoped_course(
    db: AsyncSession, university_id: str | None, course_code: str
) -> tuple[str, str | None]:
    """Resolve the course row visible to this institution, or fail loudly."""
    resolved = await find_course(db, course_code, university_id)
    if resolved is not None:
        course, effective_university_id = resolved
        return course.id, effective_university_id

    elsewhere = await course_exists_anywhere(db, course_code)
    if elsewhere and university_id:
        raise HTTPException(
            status_code=403,
            detail="This course belongs to a different institution.",
        )
    raise HTTPException(
        status_code=404,
        detail=f"Course '{course_code}' not found.",
    )


class StudyAgentRequest(BaseModel):
    course_code: str = Field(..., min_length=1, max_length=20)
    prompt: str = Field(
        default="Analyze my weaknesses and create a personalized study plan",
        max_length=2000,
    )
    task_tier: str = Field(default="standard", pattern="^(standard|complex)$")


class StudyAgentResponse(BaseModel):
    plan: str
    course_code: str
    tier: str


@router.post("/run", response_model=StudyAgentResponse)
async def run_study_agent(
    payload: StudyAgentRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(check_ai_token_quota),
):
    course_id, _course_university = await _resolve_scoped_course(
        db, user.user.university_id, payload.course_code
    )

    # task_tier arrives from the client; the expensive "complex" route
    # (Pro model) is reserved for paying users. Everyone else silently
    # gets the standard flash-tier model.
    tier = payload.task_tier
    if tier == "complex" and not await has_active_paid_pass(db, user.id):
        logger.info(
            "Complex tier requested without an active pass by user %s — downgrading to standard",
            user.id,
        )
        tier = "standard"

    try:
        # The agent runs weakness SQL + embeddings + pgvector + a long Gemini
        # generation synchronously — offload the whole pipeline to the
        # threadpool so one request never stalls the event loop.
        result = await run_in_threadpool(
            run_vylix_academic_agent,
            user_id=user.id,
            course_code=payload.course_code,
            user_prompt=payload.prompt,
            task_tier=tier,
            course_id=course_id,
        )
    except GeminiError as exc:
        status_code, detail = error_response(exc)
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception:
        logger.exception("Academic agent failed for user %s", user.id)
        raise HTTPException(
            status_code=502,
            detail="Academic agent failed. Please try again.",
        )

    return StudyAgentResponse(
        plan=result,
        course_code=payload.course_code,
        tier=tier,
    )
