"""Unique index on message_read_receipts (message_id, user_id).

Enables idempotent bulk read receipts via INSERT ... ON CONFLICT DO NOTHING
and closes the duplicate-receipt race between concurrent mark_read calls.

Revision ID: 026
Revises: 025
Create Date: 2026-08-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on = None

TABLE = "message_read_receipts"


def upgrade() -> None:
    conn = op.get_bind()
    dedupe = f"""
    DO $$
    DECLARE
        dup_count bigint;
        keeper uuid;
    BEGIN
        SELECT count(*) INTO dup_count FROM (
            SELECT 1 FROM {TABLE}
            GROUP BY message_id, user_id
            HAVING count(*) > 1
        ) d;
        IF dup_count = 0 THEN
            RETURN;
        END IF;

        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY message_id, user_id
                       ORDER BY read_at ASC NULLS LAST, id ASC
                   ) AS rn
            FROM {TABLE}
        )
        DELETE FROM {TABLE} WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
    END $$;
    """
    conn.exec_driver_sql(dedupe)
    conn.exec_driver_sql(
        f"CREATE UNIQUE INDEX IF NOT EXISTS uq_message_read_receipts_message_user "
        f"ON {TABLE} (message_id, user_id)"
    )


def downgrade() -> None:
    op.drop_index("uq_message_read_receipts_message_user", table_name=TABLE)
