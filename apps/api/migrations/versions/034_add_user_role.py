"""Add role column to users table for admin dashboard access.

Adds a ``role`` column (default ``'student'``) and a CHECK constraint
allowing only ``'student'`` or ``'admin'``.  Admin access is determined
server-side: if the user's email is in ``ADMIN_EMAILS``, the role is
auto-promoted to ``'admin'`` on first login.

Revision ID: 034
Revises: 033
Create Date: 2026-08-25
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Add role column with default
    exists = bind.exec_driver_sql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name = 'role'"
    ).scalar()
    if not exists:
        op.add_column(
            "users",
            sa.Column("role", sa.String(16), nullable=False, server_default="student"),
        )
        # CHECK constraint: only 'student' or 'admin'
        op.create_check_constraint(
            "ck_users_role",
            "users",
            "role IN ('student', 'admin')",
        )
        op.create_index("ix_users_role", "users", ["role"])


def downgrade() -> None:
    op.drop_index("ix_users_role", table_name="users")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
