"""Add ai_usage table for per-call AI cost attribution.

One row per Gemini call: user, plan snapshot, feature, model, tokens,
dedup flag, estimated cost. Also adds the missing index on
subscriptions.user_id — the quota spend path queries active passes by
user_id on every AI request.

Revision ID: 028
Revises: 027
Create Date: 2026-08-22
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guarded for environments where the table already exists via schema drift
    # (metadata create_all or manual application).
    bind = op.get_bind()
    exists = bind.exec_driver_sql(
        "SELECT to_regclass('ai_usage') IS NOT NULL"
    ).scalar()
    if not exists:
        op.create_table(
            "ai_usage",
            sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "user_id",
                sa.UUID(as_uuid=False),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("user_plan", sa.String(32), nullable=False, server_default="system"),
            sa.Column("feature", sa.String(64), nullable=False),
            sa.Column("model", sa.String(64), nullable=False),
            sa.Column("task_tier", sa.String(16), nullable=True),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("dedup_hit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("est_cost_usd", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
        )
        op.create_index("ix_ai_usage_user_created", "ai_usage", ["user_id", "created_at"])
        op.create_index("ix_ai_usage_feature_created", "ai_usage", ["feature", "created_at"])
        op.create_index("ix_ai_usage_created_at", "ai_usage", ["created_at"])

    # Hot-path companion to 027: spend_paid_query/active_passes filter by
    # user_id on every AI request.
    op.execute("CREATE INDEX IF NOT EXISTS ix_subscriptions_user_id ON subscriptions (user_id)")


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_index("ix_ai_usage_created_at", table_name="ai_usage")
    op.drop_index("ix_ai_usage_feature_created", table_name="ai_usage")
    op.drop_index("ix_ai_usage_user_created", table_name="ai_usage")
    op.drop_table("ai_usage")
