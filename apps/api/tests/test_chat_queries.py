"""Chat query rewrites: single-round-trip list, bulk receipts, grouped counts."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import event

from app.database import async_session, engine
from app.deps import CurrentUser
from app.models import (
    Conversation, ConversationMember, ConversationRole, ConversationType,
    Message, MessageReadReceipt, Notification, User,
)
from app.routers.collaboration import list_conversations, mark_read, send_message, unread_summary


def _cu(user_row: User) -> CurrentUser:
    return CurrentUser(id=user_row.id, email=None, full_name=user_row.full_name, user=user_row)


class _QueryCounter:
    def __init__(self):
        self.count = 0

    def __enter__(self):
        event.listen(engine.sync_engine, "before_cursor_execute", self._inc)
        return self

    def __exit__(self, *exc):
        event.remove(engine.sync_engine, "before_cursor_execute", self._inc)

    def _inc(self, *args, **kwargs):
        self.count += 1


async def _seed(db, n_convs: int):
    alice = User(id=str(uuid.uuid4()), full_name="Alice Sender")
    bob = User(id=str(uuid.uuid4()), full_name="Bob Reader")
    db.add_all([alice, bob])
    await db.flush()

    convs = []
    base = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)
    for i in range(n_convs):
        conv = Conversation(
            id=str(uuid.uuid4()), type=ConversationType.DIRECT,
            created_by_id=alice.id, title=f"c{i}",
        )
        convs.append(conv)
        db.add(conv)
        await db.flush()
        db.add_all([
            ConversationMember(
                id=str(uuid.uuid4()), conversation_id=conv.id, user_id=alice.id,
                role=ConversationRole.OWNER,
            ),
            # Simulate a backfilled member: both seeded messages are from
            # alice and unread by bob.
            ConversationMember(
                id=str(uuid.uuid4()), conversation_id=conv.id, user_id=bob.id,
                role=ConversationRole.MEMBER, unread_count=2,
            ),
        ])
        for j in range(2):
            db.add(Message(
                id=str(uuid.uuid4()), conversation_id=conv.id, sender_id=alice.id,
                content=f"msg {i}-{j}", created_at=base + timedelta(minutes=i * 10 + j),
            ))
        conv.updated_at = base + timedelta(minutes=i * 10)
    await db.commit()
    return alice, bob, convs


@pytest.mark.asyncio
async def test_list_conversations_single_round_trip_and_semantics(db_schema):
    try:
        async with async_session() as db:
            alice, bob, convs = await _seed(db, 3)

            with _QueryCounter() as counter:
                out = await list_conversations(user=_cu(bob), db=db)

            assert counter.count <= 2, f"expected <=2 queries, got {counter.count}"
            assert len(out) == 3
            by_id = {c.id: c for c in out}
            for i, conv in enumerate(convs):
                row = by_id[conv.id]
                assert row.unread_count == 2
                assert row.last_message == f"msg {i}-1"

            # after bob reads conversation 0, only its unread drops
            target = convs[0]
            await mark_read(
                target.id, BackgroundTasks(), user=_cu(bob), db=db
            )
            out2 = await list_conversations(user=_cu(bob), db=db)
            by_id2 = {c.id: c for c in out2}
            assert by_id2[target.id].unread_count == 0
            assert sum(c.unread_count for c in by_id2.values()) == 4
    finally:
        async with async_session() as db:
            await db.execute(MessageReadReceipt.__table__.delete())
            await db.execute(Message.__table__.delete())
            await db.execute(ConversationMember.__table__.delete())
            await db.execute(Conversation.__table__.delete())
            await db.execute(User.__table__.where(User.id.in_([])).delete())
            await db.commit()


@pytest.mark.asyncio
async def test_mark_read_bulk_and_idempotent(db_schema):
    try:
        async with async_session() as db:
            alice, bob, convs = await _seed(db, 1)
            conv = convs[0]

            await mark_read(conv.id, BackgroundTasks(), user=_cu(bob), db=db)
            await mark_read(conv.id, BackgroundTasks(), user=_cu(bob), db=db)

            rows = (await db.execute(
                MessageReadReceipt.__table__.select()
                .where(MessageReadReceipt.user_id == bob.id)
            )).all()
            assert len(rows) == 2

            member = (await db.execute(
                ConversationMember.__table__.select().where(
                    ConversationMember.conversation_id == conv.id,
                    ConversationMember.user_id == bob.id,
                )
            )).first()
            assert member.last_read_at is not None
            # Denormalized counter resets with the receipts.
            assert member.unread_count == 0
    finally:
        async with async_session() as db:
            await db.execute(MessageReadReceipt.__table__.delete())
            await db.execute(Message.__table__.delete())
            await db.execute(ConversationMember.__table__.delete())
            await db.execute(Conversation.__table__.delete())
            await db.commit()


@pytest.mark.asyncio
async def test_unread_summary_grouped_query(db_schema):
    try:
        async with async_session() as db:
            alice, bob, convs = await _seed(db, 2)

            summary = await unread_summary(user=_cu(bob), db=db)
            assert summary["unread_messages"] == 4

            await mark_read(convs[0].id, BackgroundTasks(), user=_cu(bob), db=db)
            summary2 = await unread_summary(user=_cu(bob), db=db)
            assert summary2["unread_messages"] == 2
    finally:
        async with async_session() as db:
            await db.execute(MessageReadReceipt.__table__.delete())
            await db.execute(Message.__table__.delete())
            await db.execute(ConversationMember.__table__.delete())
            await db.execute(Conversation.__table__.delete())
            await db.commit()


@pytest.mark.asyncio
async def test_send_message_still_works_after_rewrite(db_schema):
    try:
        async with async_session() as db:
            from app.schemas import MessageCreate

            alice, bob, convs = await _seed(db, 1)
            out = await send_message(
                convs[0].id, MessageCreate(content="hello"),
                BackgroundTasks(), user=_cu(alice), db=db,
            )
            assert out.content == "hello"
            assert out.sender_id == alice.id

            # Recipient's denormalized counter was bumped.
            member = (await db.execute(
                ConversationMember.__table__.select().where(
                    ConversationMember.conversation_id == convs[0].id,
                    ConversationMember.user_id == bob.id,
                )
            )).first()
            assert member.unread_count == 3
    finally:
        async with async_session() as db:
            await db.execute(MessageReadReceipt.__table__.delete())
            await db.execute(Notification.__table__.delete())
            await db.execute(Message.__table__.delete())
            await db.execute(ConversationMember.__table__.delete())
            await db.execute(Conversation.__table__.delete())
            await db.commit()


@pytest.mark.asyncio
async def test_send_message_collapses_notifications_per_conversation(db_schema):
    try:
        async with async_session() as db:
            from app.schemas import MessageCreate

            alice, bob, convs = await _seed(db, 1)
            conv = convs[0]

            await send_message(
                conv.id, MessageCreate(content="first"),
                BackgroundTasks(), user=_cu(alice), db=db,
            )
            await send_message(
                conv.id, MessageCreate(content="second"),
                BackgroundTasks(), user=_cu(alice), db=db,
            )

            notifs = (await db.execute(
                Notification.__table__.select().where(Notification.user_id == bob.id)
            )).all()
            # One collapsed row per (user, conversation), previewing the newest message.
            assert len(notifs) == 1
            assert notifs[0].message == "second"
            assert str(notifs[0].conversation_id) == conv.id
    finally:
        async with async_session() as db:
            await db.execute(MessageReadReceipt.__table__.delete())
            await db.execute(Notification.__table__.delete())
            await db.execute(Message.__table__.delete())
            await db.execute(ConversationMember.__table__.delete())
            await db.execute(Conversation.__table__.delete())
            await db.commit()


@pytest.mark.asyncio
async def test_delete_message_decrements_only_unread_recipients(db_schema):
    try:
        async with async_session() as db:
            from app.schemas import MessageCreate
            from app.routers.collaboration import delete_message

            alice, bob, convs = await _seed(db, 1)
            conv = convs[0]
            out = await send_message(
                conv.id, MessageCreate(content="to be deleted"),
                BackgroundTasks(), user=_cu(alice), db=db,
            )

            member = (await db.execute(
                ConversationMember.__table__.select().where(
                    ConversationMember.conversation_id == conv.id,
                    ConversationMember.user_id == bob.id,
                )
            )).first()
            assert member.unread_count == 3

            # Bob reads first; deleting the unread message must not pull his
            # counter below what he actually read.
            await mark_read(conv.id, BackgroundTasks(), user=_cu(bob), db=db)
            await delete_message(out.id, BackgroundTasks(), user=_cu(alice), db=db)

            member2 = (await db.execute(
                ConversationMember.__table__.select().where(
                    ConversationMember.conversation_id == conv.id,
                    ConversationMember.user_id == bob.id,
                )
            )).first()
            assert member2.unread_count == 0
    finally:
        async with async_session() as db:
            await db.execute(MessageReadReceipt.__table__.delete())
            await db.execute(Notification.__table__.delete())
            await db.execute(Message.__table__.delete())
            await db.execute(ConversationMember.__table__.delete())
            await db.execute(Conversation.__table__.delete())
            await db.commit()
