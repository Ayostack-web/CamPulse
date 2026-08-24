from __future__ import annotations

from pydantic import BaseModel


class StreakOut(BaseModel):
    current_streak: int = 0
    longest_streak: int = 0
    last_activity_at: str | None = None


class StreakWithPointsOut(BaseModel):
    current_streak: int = 0
    longest_streak: int = 0
    last_activity_at: str | None = None
    total_points: int = 0


class PointsOut(BaseModel):
    total_points: int = 0
    spendable_points: int = 0


class TransactionOut(BaseModel):
    id: str
    amount: int
    reason: str
    description: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    user_id: str
    full_name: str
    avatar_url: str | None = None
    value: int


class ContributionLeaderboardEntry(BaseModel):
    user_id: str
    full_name: str
    avatar_url: str | None = None
    contribution_score: int


class QuestionCreate(BaseModel):
    title: str
    content: str


class AnswerCreate(BaseModel):
    content: str


class ConversationCreate(BaseModel):
    type: str = "DIRECT"
    title: str | None = None
    member_ids: list[str] = []
    department_id: str | None = None
    topic_id: str | None = None


class MessageCreate(BaseModel):
    content: str
    metadata: dict | None = None
