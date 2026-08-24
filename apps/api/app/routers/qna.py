from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import CurrentUser, get_current_user
from app.models import (
    TopicQuestion, QuestionAnswer, Topic, User,
    PointsTransaction, User as UserModel, Notification,
)
from app.schemas import QuestionCreate, AnswerCreate

router = APIRouter(prefix="/qna", tags=["qna"])


class AnswerOut(BaseModel):
    id: str
    question_id: str
    author_id: str
    content: str
    help_count: int = 0
    is_accepted: bool = False
    created_at: str | None = None

    model_config = {"from_attributes": True}


class QuestionOut(BaseModel):
    id: str
    topic_id: str
    author_id: str
    title: str
    content: str
    help_count: int = 0
    view_count: int = 0
    is_resolved: bool = False
    created_at: str | None = None
    answers: list[AnswerOut] = []

    model_config = {"from_attributes": True}


@router.post("/topics/{topic_id}/questions", response_model=QuestionOut)
async def create_question(
    topic_id: str,
    payload: QuestionCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    q = TopicQuestion(
        id=str(uuid.uuid4()), topic_id=topic_id, author_id=user.id,
        title=payload.title, content=payload.content,
    )
    db.add(q)
    user.user.contribution_score += 5
    db.add(PointsTransaction(user_id=user.id, amount=5, reason="ask_question", related_id=q.id))
    await db.flush()
    return QuestionOut(
        id=q.id, topic_id=q.topic_id, author_id=q.author_id,
        title=q.title, content=q.content, help_count=q.help_count,
        view_count=q.view_count, is_resolved=q.is_resolved,
        created_at=str(q.created_at) if q.created_at else None,
    )


@router.get("/topics/{topic_id}/questions", response_model=list[QuestionOut])
async def list_questions(
    topic_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # selectinload fetches all answers in one extra query — the previous
    # per-question loop was a textbook N+1.
    result = await db.execute(
        select(TopicQuestion)
        .options(selectinload(TopicQuestion.answers))
        .where(TopicQuestion.topic_id == topic_id)
        .order_by(TopicQuestion.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    questions = result.scalars().unique().all()
    out = []
    for q in questions:
        answers = sorted(q.answers, key=lambda a: a.is_accepted, reverse=True)
        out.append(QuestionOut(
            id=q.id, topic_id=q.topic_id, author_id=q.author_id,
            title=q.title, content=q.content, help_count=q.help_count,
            view_count=q.view_count, is_resolved=q.is_resolved,
            created_at=str(q.created_at) if q.created_at else None,
            answers=[AnswerOut(
                id=a.id, question_id=a.question_id, author_id=a.author_id,
                content=a.content, help_count=a.help_count, is_accepted=a.is_accepted,
                created_at=str(a.created_at) if a.created_at else None,
            ) for a in answers],
        ))
    return out


@router.post("/questions/{question_id}/answers", response_model=AnswerOut)
async def create_answer(
    question_id: str,
    payload: AnswerCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = await db.get(TopicQuestion, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    a = QuestionAnswer(id=str(uuid.uuid4()), question_id=question_id, author_id=user.id, content=payload.content)
    db.add(a)
    user.user.contribution_score += 10
    db.add(PointsTransaction(user_id=user.id, amount=10, reason="answer_question", related_id=a.id))

    if q.author_id != user.id:
        notif = Notification(
            id=str(uuid.uuid4()), user_id=q.author_id,
            kind="qa_reply", title="New answer to your question",
            message=f"{user.full_name} answered: {q.title}",
            payload={"question_id": q.id, "answer_id": a.id},
        )
        db.add(notif)

    await db.flush()
    return AnswerOut(
        id=a.id, question_id=a.question_id, author_id=a.author_id,
        content=a.content, help_count=a.help_count, is_accepted=a.is_accepted,
        created_at=str(a.created_at) if a.created_at else None,
    )


@router.post("/answers/{answer_id}/helpful")
async def mark_helpful(
    answer_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = await db.get(QuestionAnswer, answer_id)
    if not a:
        raise HTTPException(status_code=404, detail="Answer not found")
    a.help_count += 1
    # Award points to answer author (max 50 per answer)
    if a.help_count <= 50:
        author = await db.get(UserModel, a.author_id)
        if author:
            author.contribution_score += 2
            db.add(PointsTransaction(user_id=a.author_id, amount=2, reason="answer_marked_helpful", related_id=answer_id))
    await db.flush()
    return {"message": "Marked helpful", "help_count": a.help_count}


@router.post("/questions/{qid}/answers/{aid}/accept")
async def accept_answer(
    qid: str,
    aid: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = await db.get(TopicQuestion, qid)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    if q.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only question author can accept")

    a = await db.get(QuestionAnswer, aid)
    if not a or a.question_id != qid:
        raise HTTPException(status_code=404, detail="Answer not found")

    a.is_accepted = True
    q.is_resolved = True
    author = await db.get(UserModel, a.author_id)
    if author:
        author.contribution_score += 25
        db.add(PointsTransaction(user_id=a.author_id, amount=25, reason="answer_accepted", related_id=aid))

    if a.author_id != user.id:
        notif = Notification(
            id=str(uuid.uuid4()), user_id=a.author_id,
            kind="answer_accepted", title="Your answer was accepted!",
            message=f"Your answer to '{q.title}' was marked as the best answer.",
            payload={"question_id": q.id, "answer_id": a.id},
        )
        db.add(notif)

    await db.flush()
    return {"message": "Answer accepted"}


@router.get("/trending", response_model=list[QuestionOut])
async def trending_questions(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import timedelta
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    result = await db.execute(
        select(TopicQuestion)
        .where(TopicQuestion.created_at >= week_ago)
        .order_by(desc(TopicQuestion.help_count + TopicQuestion.view_count))
        .limit(20)
    )
    return [
        QuestionOut(
            id=q.id, topic_id=q.topic_id, author_id=q.author_id,
            title=q.title, content=q.content, help_count=q.help_count,
            view_count=q.view_count, is_resolved=q.is_resolved,
            created_at=str(q.created_at) if q.created_at else None,
        )
        for q in result.scalars().all()
    ]


@router.get("/search", response_model=list[QuestionOut])
async def search_questions(
    q: str = Query(...),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TopicQuestion)
        .where(TopicQuestion.title.ilike(f"%{q}%") | TopicQuestion.content.ilike(f"%{q}%"))
        .order_by(TopicQuestion.created_at.desc())
        .limit(20)
    )
    return [
        QuestionOut(
            id=q_.id, topic_id=q_.topic_id, author_id=q_.author_id,
            title=q_.title, content=q_.content, help_count=q_.help_count,
            view_count=q_.view_count, is_resolved=q_.is_resolved,
            created_at=str(q_.created_at) if q_.created_at else None,
        )
        for q_ in result.scalars().all()
    ]


class TopAnswererOut(BaseModel):
    user_id: str
    answer_count: int
    helpful_count: int


@router.get("/topics/{topic_id}/top-answerers", response_model=list[TopAnswererOut])
async def top_answerers(
    topic_id: str,
    limit: int = Query(default=5, ge=1, le=20),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            QuestionAnswer.author_id,
            func.count(QuestionAnswer.id).label("answer_count"),
            func.coalesce(func.sum(QuestionAnswer.help_count), 0).label("helpful_count"),
        )
        .join(TopicQuestion, TopicQuestion.id == QuestionAnswer.question_id)
        .where(TopicQuestion.topic_id == topic_id)
        .group_by(QuestionAnswer.author_id)
        .order_by(desc("helpful_count"))
        .limit(limit)
    )
    return [
        TopAnswererOut(user_id=uid, answer_count=ac, helpful_count=hc)
        for uid, ac, hc in result.all()
    ]
