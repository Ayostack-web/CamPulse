from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select, true, update
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import CurrentUser, get_current_user
from app.models import (
    Conversation, ConversationMember, Message, MessageReadReceipt,
    Notification, User, ConversationType, ConversationRole,
)
from app.schemas import ConversationCreate, MessageCreate
from app.services.realtime import publish_event

router = APIRouter(prefix="/collaboration", tags=["collaboration"])


class ConversationOut(BaseModel):
    id: str
    type: str
    title: str | None = None
    created_by_id: str
    created_at: str | None = None
    updated_at: str | None = None
    unread_count: int = 0
    last_message: str | None = None

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    content: str
    metadata: dict | None = None
    edited_at: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class NotificationOut(BaseModel):
    id: str
    kind: str
    title: str
    message: str | None = None
    payload: dict | None = None
    read_at: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class UserSearchResult(BaseModel):
    id: str
    full_name: str
    avatar_url: str | None = None
    matric_number: str | None = None


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(
    payload: ConversationCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv_type = ConversationType.DIRECT if payload.type == "DIRECT" else ConversationType.GROUP
    conv = Conversation(
        id=str(uuid.uuid4()), type=conv_type, title=payload.title,
        department_id=payload.department_id, topic_id=payload.topic_id,
        created_by_id=user.id,
    )
    db.add(conv)
    await db.flush()

    owner = ConversationMember(
        id=str(uuid.uuid4()), conversation_id=conv.id,
        user_id=user.id, role=ConversationRole.OWNER,
    )
    db.add(owner)

    for mid in payload.member_ids:
        if mid != user.id:
            member = ConversationMember(
                id=str(uuid.uuid4()), conversation_id=conv.id,
                user_id=mid, role=ConversationRole.MEMBER,
            )
            db.add(member)
    await db.flush()
    return ConversationOut(
        id=conv.id, type=conv.type.value, title=conv.title,
        created_by_id=conv.created_by_id,
        created_at=str(conv.created_at) if conv.created_at else None,
        updated_at=str(conv.updated_at) if conv.updated_at else None,
    )


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
):
    # Latest message per conversation via a lateral join: one index scan per
    # row instead of a correlated scalar subquery.
    last_msg = (
        select(Message.content)
        .where(
            Message.conversation_id == Conversation.id,
            Message.deleted_at == None,
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
        .lateral("last_msg")
    )

    rows = await db.execute(
        select(Conversation, ConversationMember.unread_count, last_msg.c.content)
        .join(
            ConversationMember,
            (ConversationMember.conversation_id == Conversation.id)
            & (ConversationMember.user_id == user.id),
        )
        .outerjoin(last_msg, true())
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    return [
        ConversationOut(
            id=c.id, type=c.type.value, title=c.title,
            created_by_id=c.created_by_id,
            created_at=str(c.created_at) if c.created_at else None,
            updated_at=str(c.updated_at) if c.updated_at else None,
            unread_count=unread or 0,
            last_message=last_msg_content,
        )
        for c, unread, last_msg_content in rows.all()
    ]


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conv_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    after: datetime | None = Query(default=None),
    before: datetime | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify membership
    mem = await db.execute(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conv_id,
            ConversationMember.user_id == user.id,
        )
    )
    if not mem.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member")

    if after is not None:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id, Message.created_at > after)
            .order_by(Message.created_at.asc())
            .limit(200)
        )
        msgs = result.scalars().all()
        return [
            MessageOut(
                id=m.id, conversation_id=m.conversation_id, sender_id=m.sender_id,
                content=m.content, metadata=m.meta, edited_at=str(m.edited_at) if m.edited_at else None,
                deleted_at=str(m.deleted_at) if m.deleted_at else None,
                created_at=str(m.created_at) if m.created_at else None,
            )
            for m in msgs
        ]

    if before is not None:
        # Cursor page for infinite scroll: the `limit` messages strictly older
        # than the cursor, oldest-first so pages prepend cleanly.
        result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == conv_id,
                Message.deleted_at == None,
                Message.created_at < before,
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        msgs = list(reversed(result.scalars().all()))
        return [
            MessageOut(
                id=m.id, conversation_id=m.conversation_id, sender_id=m.sender_id,
                content=m.content, metadata=m.meta, edited_at=str(m.edited_at) if m.edited_at else None,
                deleted_at=str(m.deleted_at) if m.deleted_at else None,
                created_at=str(m.created_at) if m.created_at else None,
            )
            for m in msgs
        ]

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id, Message.deleted_at == None)
        .order_by(Message.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return [
        MessageOut(
            id=m.id, conversation_id=m.conversation_id, sender_id=m.sender_id,
            content=m.content, metadata=m.meta, edited_at=str(m.edited_at) if m.edited_at else None,
            deleted_at=str(m.deleted_at) if m.deleted_at else None,
            created_at=str(m.created_at) if m.created_at else None,
        )
        for m in result.scalars().all()
    ]


def _message_event(msg: Message) -> dict:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "sender_id": msg.sender_id,
        "content": msg.content,
        "metadata": msg.meta,
        "edited_at": str(msg.edited_at) if msg.edited_at else None,
        "deleted_at": str(msg.deleted_at) if msg.deleted_at else None,
        "created_at": str(msg.created_at) if msg.created_at else None,
    }


@router.post("/conversations/{conv_id}/messages", response_model=MessageOut)
async def send_message(
    conv_id: str,
    payload: MessageCreate,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mem = await db.execute(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conv_id,
            ConversationMember.user_id == user.id,
        )
    )
    if not mem.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member")

    msg = Message(
        id=str(uuid.uuid4()), conversation_id=conv_id,
        sender_id=user.id, content=payload.content, meta=payload.metadata,
    )
    db.add(msg)

    # Create notifications for other members
    members = await db.execute(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conv_id,
            ConversationMember.user_id != user.id,
        )
    )
    recipient_ids: list[str] = []
    for m in members.scalars().all():
        recipient_ids.append(m.user_id)

    # Denormalized unread counters: one bulk bump instead of recomputing
    # anti-joins over messages x receipts on every listing.
    if recipient_ids:
        await db.execute(
            update(ConversationMember)
            .where(
                ConversationMember.conversation_id == conv_id,
                ConversationMember.user_id.in_(recipient_ids),
            )
            .values(unread_count=ConversationMember.unread_count + 1)
        )

        # One collapsed "message" notification per (user, conversation),
        # upserted in place instead of inserting a row per message.
        now = datetime.now(timezone.utc)
        preview = payload.content[:100]
        await db.execute(
            pg_insert(Notification.__table__)
            .values([
                {
                    "id": str(uuid.uuid4()),
                    "user_id": rid,
                    "kind": "message",
                    "title": "New message",
                    "message": preview,
                    "payload": {"conversation_id": conv_id},
                    "source_message_id": msg.id,
                    "conversation_id": conv_id,
                    "delivered_at": now,
                    "created_at": now,
                }
                for rid in recipient_ids
            ])
            .on_conflict_do_update(
                index_elements=["user_id", "kind", "conversation_id"],
                index_where=Notification.__table__.c.conversation_id.isnot(None),
                set_={
                    "title": "New message",
                    "message": preview,
                    "source_message_id": msg.id,
                    "created_at": now,
                    "read_at": None,
                },
            )
        )

    await db.flush()
    event_data = _message_event(msg)
    background_tasks.add_task(publish_event, f"conversation:{conv_id}", "message:new", event_data)
    for rid in recipient_ids:
        background_tasks.add_task(
            publish_event, f"user:{rid}", "unread:update",
            {"conversation_id": conv_id, "message_id": msg.id},
        )
    return MessageOut(
        id=msg.id, conversation_id=msg.conversation_id, sender_id=msg.sender_id,
        content=msg.content, metadata=msg.meta,
        created_at=str(msg.created_at) if msg.created_at else None,
    )


@router.patch("/messages/{msg_id}")
async def edit_message(
    msg_id: str,
    content: str,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await db.get(Message, msg_id)
    if not msg or msg.sender_id != user.id:
        raise HTTPException(status_code=403, detail="Cannot edit")
    msg.content = content
    msg.edited_at = datetime.now(timezone.utc)
    await db.flush()
    background_tasks.add_task(
        publish_event, f"conversation:{msg.conversation_id}", "message:update", _message_event(msg)
    )
    return {"message": "Edited"}


@router.delete("/messages/{msg_id}")
async def delete_message(
    msg_id: str,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await db.get(Message, msg_id)
    if not msg or msg.sender_id != user.id:
        raise HTTPException(status_code=403, detail="Cannot delete")
    was_visible = msg.deleted_at is None
    msg.deleted_at = datetime.now(timezone.utc)
    if was_visible:
        # Pull the message back out of recipients' unread counters, but only
        # for members who had not read it yet.
        await db.execute(
            sa_text(
                """
                UPDATE conversation_members cm
                SET unread_count = GREATEST(cm.unread_count - 1, 0)
                WHERE cm.conversation_id = :conv_id
                  AND cm.user_id <> :sender_id
                  AND cm.unread_count > 0
                  AND NOT EXISTS (
                      SELECT 1 FROM message_read_receipts r
                      WHERE r.message_id = :message_id AND r.user_id = cm.user_id
                  )
                """
            ),
            {"conv_id": msg.conversation_id, "sender_id": user.id, "message_id": msg.id},
        )
    await db.flush()
    background_tasks.add_task(
        publish_event, f"conversation:{msg.conversation_id}", "message:update", _message_event(msg)
    )
    return {"message": "Deleted"}


@router.post("/conversations/{conv_id}/read")
async def mark_read(
    conv_id: str,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Message.id)
        .where(Message.conversation_id == conv_id, Message.deleted_at == None)
        .order_by(Message.created_at.desc())
        .limit(50)
    )
    msg_ids = [r[0] for r in result.all()]
    if msg_ids:
        await db.execute(
            pg_insert(MessageReadReceipt.__table__)
            .values([
                {"id": str(uuid.uuid4()), "message_id": mid, "user_id": user.id}
                for mid in msg_ids
            ])
            .on_conflict_do_nothing(index_elements=["message_id", "user_id"])
        )

    # Update member's last_read_at
    mem = await db.execute(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conv_id,
            ConversationMember.user_id == user.id,
        )
    )
    member = mem.scalar_one_or_none()
    if member:
        member.last_read_at = datetime.now(timezone.utc)
        member.unread_count = 0

    await db.flush()
    background_tasks.add_task(
        publish_event, f"conversation:{conv_id}", "read",
        {"conversation_id": conv_id, "user_id": user.id},
    )
    return {"message": "Marked read"}


@router.get("/unread-summary")
async def unread_summary(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # O(memberships) sum over denormalized counters instead of an anti-join
    # across every message in every conversation.
    total_unread = await db.scalar(
        select(func.coalesce(func.sum(ConversationMember.unread_count), 0))
        .where(ConversationMember.user_id == user.id)
    )

    notif_count = await db.execute(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at == None)
    )
    return {"unread_messages": total_unread or 0, "unread_notifications": notif_count.scalar() or 0}


@router.get("/users/search", response_model=list[UserSearchResult])
async def search_users(
    q: str = Query(...),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(
            or_(
                User.full_name.ilike(f"%{q}%"),
                User.matric_number.ilike(f"%{q}%"),
            )
        ).limit(20)
    )
    return [
        UserSearchResult(id=u.id, full_name=u.full_name, avatar_url=u.avatar_url, matric_number=u.matric_number)
        for u in result.scalars().all()
    ]


@router.get("/users/classmates", response_model=list[UserSearchResult])
async def classmates(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    u = user.user
    if not u.department_id or not u.current_level:
        return []
    result = await db.execute(
        select(User).where(
            User.department_id == u.department_id,
            User.current_level == u.current_level,
            User.id != user.id,
        ).limit(50)
    )
    return [
        UserSearchResult(id=u.id, full_name=u.full_name, avatar_url=u.avatar_url, matric_number=u.matric_number)
        for u in result.scalars().all()
    ]


@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
    )
    return [
        NotificationOut(
            id=n.id, kind=n.kind, title=n.title, message=n.message,
            payload=n.payload, read_at=str(n.read_at) if n.read_at else None,
            created_at=str(n.created_at) if n.created_at else None,
        )
        for n in result.scalars().all()
    ]


@router.post("/notifications/{notif_id}/read")
async def mark_notification_read(
    notif_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notif = await db.get(Notification, notif_id)
    if not notif or notif.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    notif.read_at = datetime.now(timezone.utc)
    await db.flush()
    return {"message": "Marked read"}


class TypingPayload(BaseModel):
    is_typing: bool = False


@router.post("/conversations/{conv_id}/typing")
async def send_typing_indicator(
    conv_id: str,
    payload: TypingPayload,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member = await db.execute(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conv_id,
            ConversationMember.user_id == user.id,
        )
    )
    if not member.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this conversation")
    background_tasks.add_task(
        publish_event, f"conversation:{conv_id}", "typing",
        {"conversation_id": conv_id, "user_id": user.id, "is_typing": payload.is_typing},
    )
    return {"conversation_id": conv_id, "user_id": user.id, "is_typing": payload.is_typing}
