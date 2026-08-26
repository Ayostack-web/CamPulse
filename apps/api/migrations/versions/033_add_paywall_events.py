"""Add paywall_events table for conversion funnel tracking.

Records paywall impressions, plan clicks, checkout attempts, and
completions. Best-effort logging — failed inserts never block requests.

Revision ID: 033
Revises: 032
Create Date: 2026-08-25
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.exec_driver_sql(
        "SELECT to_regclass('paywall_events') IS NOT NULL"
    ).scalar()
    if not exists:
        op.create_table(
            "paywall_events",
            sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "user_id",
                sa.UUID(as_uuid=False),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("event_type", sa.String(32), nullable=False),
            sa.Column("plan_key", sa.String(32), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
        )
        op.create_index("ix_paywall_events_user_created", "paywall_events", ["user_id", "created_at"])
        op.create_index("ix_paywall_events_type_created", "paywall_events", ["event_type", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_paywall_events_type_created", table_name="paywall_events")
    op.drop_index("ix_paywall_events_user_created", table_name="paywall_events")
    op.drop_table("paywall_events")
