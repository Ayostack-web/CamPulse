"""Denormalize chat unread counts and collapse per-message notifications.

conversation_members.unread_count replaces the anti-join count recomputed on
every conversations listing; notifications for chat messages are collapsed to
one row per (user, conversation) instead of one row per message x member.

Revision ID: 031
Revises: 030
Create Date: 2026-08-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on = None


def _exec(sql: str) -> None:
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
    _exec(
        "ALTER TABLE conversation_members "
        "ADD COLUMN IF NOT EXISTS unread_count INTEGER NOT NULL DEFAULT 0"
    )

    # Backfill from the source of truth (messages + read receipts).
    _exec(
        """
        UPDATE conversation_members cm
        SET unread_count = COALESCE(sub.unread, 0)
        FROM (
            SELECT cm2.id AS member_id, count(m.id) AS unread
            FROM conversation_members cm2
            JOIN messages m
              ON m.conversation_id = cm2.conversation_id
             AND m.sender_id <> cm2.user_id
             AND m.deleted_at IS NULL
             AND NOT EXISTS (
                 SELECT 1 FROM message_read_receipts r
                 WHERE r.message_id = m.id AND r.user_id = cm2.user_id
             )
            GROUP BY cm2.id
        ) sub
        WHERE cm.id = sub.member_id
        """
    )

    _exec(
        "ALTER TABLE notifications "
        "ADD COLUMN IF NOT EXISTS conversation_id UUID "
        "REFERENCES conversations(id) ON DELETE CASCADE"
    )
    _exec(
        "CREATE INDEX IF NOT EXISTS ix_notifications_conversation_id "
        "ON notifications (conversation_id)"
    )

    has_conv_col = op.get_bind().exec_driver_sql(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'notifications' AND column_name = 'conversation_id'
        """
    ).fetchone()
    if has_conv_col:
        # Attach existing chat notifications to their conversation.
        _exec(
            """
            UPDATE notifications n
            SET conversation_id = m.conversation_id
            FROM messages m
            WHERE n.source_message_id = m.id
              AND n.kind = 'message'
              AND n.conversation_id IS NULL
            """
        )
        # Collapse to the newest notification per (user, conversation).
        _exec(
            """
            DELETE FROM notifications n
            USING notifications keeper
            WHERE n.kind = 'message'
              AND keeper.kind = 'message'
              AND n.user_id = keeper.user_id
              AND n.conversation_id IS NOT NULL
              AND keeper.conversation_id = n.conversation_id
              AND (keeper.created_at, keeper.id) > (n.created_at, n.id)
            """
        )

    _exec(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_user_kind_conversation "
        "ON notifications (user_id, kind, conversation_id) "
        "WHERE conversation_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("uq_notifications_user_kind_conversation", table_name="notifications")
    op.drop_index("ix_notifications_conversation_id", table_name="notifications")
    op.drop_column("notifications", "conversation_id")
    op.drop_column("conversation_members", "unread_count")
